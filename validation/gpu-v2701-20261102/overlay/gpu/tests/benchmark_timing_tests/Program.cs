using System.Text.Json;
using GRAL_2001;

int checks = 0;
void Check(bool ok, string label) { if (!ok) throw new Exception("FAIL: " + label); checks++; }
void Throws(Action run, string label) { bool threw = false; try { run(); } catch { threw = true; } Check(threw, label); }
var untouched = new List<string>();
Check(BenchmarkTelemetry.FromEnvironment(0, 0, key => { untouched.Add(key); return null; }) == null, "disabled observer is null");
Check(untouched.SequenceEqual(new[] { "INU_BENCH_TIMING" }), "disabled observer ignores all other configuration");

string folder = Path.Combine(AppContext.BaseDirectory, "test-files-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(folder);
string path = Path.Combine(folder, "timing.jsonl");
var env = new Dictionary<string, string> { ["INU_BENCH_TIMING"] = path, ["INU_BENCH_WARMUP"] = "3", ["INU_BENCH_END"] = "24" };
string Read(string key) => env.GetValueOrDefault(key);
foreach (string bad in new[] { "", "relative.jsonl" }) { env["INU_BENCH_TIMING"] = bad; Throws(() => BenchmarkTelemetry.FromEnvironment(1, 24, Read), "invalid path"); }
env["INU_BENCH_TIMING"] = path;
foreach (string bad in new[] { "", "0", "4" }) { env["INU_BENCH_WARMUP"] = bad; Throws(() => BenchmarkTelemetry.FromEnvironment(1, 24, Read), "invalid warmup"); }
env["INU_BENCH_WARMUP"] = "3";
foreach (string bad in new[] { "", "23", "49", "024" }) { env["INU_BENCH_END"] = bad; Throws(() => BenchmarkTelemetry.FromEnvironment(1, 24, Read), "invalid end"); }
env["INU_BENCH_END"] = "24";
Throws(() => BenchmarkTelemetry.FromEnvironment(0, 24, Read), "explicit start required");
Throws(() => BenchmarkTelemetry.FromEnvironment(1, 48, Read), "end mismatch");
Check(!File.Exists(path), "invalid config never writes file");
var actual = BenchmarkTelemetry.FromEnvironment(1, 24, Read);
actual.Finish();
Check(File.ReadAllLines(path).Length == 2, "real append includes config and incomplete");
Throws(() => BenchmarkTelemetry.FromEnvironment(1, 24, Read), "existing log rejected");

foreach (int end in new[] { 24, 48 })
{
    long ticks = 100;
    var lines = new List<string>();
    var drains = new List<int>();
    var observer = new BenchmarkTelemetry(3, end, lines.Add, () => ticks, 10);
    double total = 0, warmup = 0;
    for (int i = 1; i <= end; i++)
    {
        double duration = 3600 + i; total += duration;
        observer.RecordSeed(i, duration, 1.25f, -90f, (uint)(100 + i), (uint)(200 + i), true);
        ticks += 20;
        observer.CompleteSituation(i, () => { drains.Add(i); ticks += 7; });
        if (i == 3) warmup = total;
    }
    observer.Finish();
    var json = lines.Select(x => JsonDocument.Parse(x).RootElement.Clone()).ToArray();
    var seeds = json.Where(x => x.GetProperty("event_type").GetString() == "seed").ToArray();
    var bounds = json.Where(x => x.GetProperty("event_type").GetString() == "boundary").ToArray();
    Check(drains.SequenceEqual(new[] { 3, end }), "only warmup and final output drains");
    Check(seeds.Length == end, "one seed per hour");
    Check(bounds.Length == 2, "two boundaries only");
    Check(bounds[0].GetProperty("stopwatch_timestamp").GetInt64() == 167, "start includes completed warmup drain");
    Check(bounds[1].GetProperty("elapsed_s").GetDouble() == ((end - 3) * 20 + 7) / 10.0, "elapsed includes final drain");
    Check(bounds[1].GetProperty("cumulative_model_seconds").GetDouble() == total, "cumulative TAUS exact");
    Check(bounds[1].GetProperty("measured_model_seconds").GetDouble() == total - warmup, "measured TAUS excludes warmup");
    Check(bounds[1].GetProperty("measured_situations").GetInt32() == end - 3, "measured situation count");
    Check(json[^1].GetProperty("complete").GetBoolean(), "finish complete");
    Check(seeds.All(x => x.EnumerateObject().Select(p => p.Name).SequenceEqual(new[] { "event_type", "IWET", "TAUS", "WindVelGral", "WindDirGral", "Seed1", "Seed2", "fixed_mode", "stopwatch_timestamp" })), "same full seed schema every hour");
    Check(seeds[0].GetProperty("Seed1").GetUInt32() == 101 && seeds[^1].GetProperty("WindDirGral").GetSingle() == -90f, "seed and meteorology preserved");
}
var unfinishedLines = new List<string>();
var unfinished = new BenchmarkTelemetry(3, 24, unfinishedLines.Add, () => 0, 1);
Throws(() => unfinished.RecordSeed(2, 3600, 1, 1, 1, 1, true), "skip first situation rejected");
Throws(() => unfinished.RecordSeed(1, double.NaN, 1, 1, 1, 1, true), "nonfinite TAUS rejected");
unfinished.RecordSeed(1, 3600, 1, 1, 1, 1, false);
Throws(() => unfinished.RecordSeed(2, 3600, 1, 1, 1, 1, false), "seed without completion rejected");
unfinished.CompleteSituation(1, () => throw new Exception("middle hour must not drain"));
Throws(() => unfinished.CompleteSituation(1, () => { }), "duplicate completion rejected");
unfinished.Finish();
Check(JsonDocument.Parse(unfinishedLines[^1]).RootElement.GetProperty("event_type").GetString() == "incomplete", "requested end missing explicitly reported");
var failedDrainLines = new List<string>();
var failedDrain = new BenchmarkTelemetry(3, 24, failedDrainLines.Add, () => 0, 1);
for (int i = 1; i <= 2; i++) { failedDrain.RecordSeed(i, 1, 1, 1, 1, 1, true); failedDrain.CompleteSituation(i, () => { }); }
failedDrain.RecordSeed(3, 1, 1, 1, 1, 1, true);
Throws(() => failedDrain.CompleteSituation(3, () => throw new IOException("writer failure")), "drain errors propagate");
Check(!failedDrainLines.Any(x => x.Contains("\"boundary\"")), "failed drain never publishes boundary");
Console.WriteLine($"PASS {checks} checks; no model or GPU execution");
Console.WriteLine("test_artifacts " + folder);
