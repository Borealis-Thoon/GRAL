using System;
using System.Diagnostics;
using System.IO;
using System.Text.Json;

namespace GRAL_2001
{
    // Optional observer shared by CPU/GPU; it never reads model state or changes seeds.
    internal sealed class BenchmarkTelemetry
    {
        private readonly int warmup;
        private readonly int end;
        private readonly Action<string> append;
        private readonly Func<long> timestamp;
        private readonly long frequency;
        private int seeded;
        private int completed;
        private double pendingModelSeconds;
        private double modelSeconds;
        private double warmupModelSeconds;
        private long startTimestamp;
        private bool started;
        private bool stopped;

        internal BenchmarkTelemetry(int warmup, int end, Action<string> append, Func<long> timestamp, long frequency)
        {
            if (warmup != 3 || (end != 24 && end != 48) || frequency <= 0)
                throw new ArgumentException("Benchmark requires warmup=3, end=24 or 48 and a positive clock frequency.");
            this.warmup = warmup;
            this.end = end;
            this.append = append;
            this.timestamp = timestamp;
            this.frequency = frequency;
            Write(new { event_type = "config", warmup, end, stopwatch_frequency = frequency });
        }

        internal static BenchmarkTelemetry FromEnvironment(int firstSituation, int lastSituation,
            Func<string, string> readEnvironment = null)
        {
            readEnvironment ??= Environment.GetEnvironmentVariable;
            string path = readEnvironment("INU_BENCH_TIMING");
            if (path == null) return null;
            string endText = readEnvironment("INU_BENCH_END");
            if (string.IsNullOrWhiteSpace(path) || !Path.IsPathFullyQualified(path) ||
                readEnvironment("INU_BENCH_WARMUP") != "3" || (endText != "24" && endText != "48"))
                throw new ArgumentException("INU_BENCH_TIMING requires a new absolute file path, INU_BENCH_WARMUP=3 and INU_BENCH_END=24 or 48.");
            int end = int.Parse(endText, System.Globalization.CultureInfo.InvariantCulture);
            if (firstSituation != 1 || lastSituation != end)
                throw new ArgumentException("Benchmark requires explicit command-line situation range 1 through INU_BENCH_END.");
            // A stale log must never be mistaken for a completed new benchmark.
            using (new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read)) { }
            return new BenchmarkTelemetry(3, end, line => File.AppendAllText(path, line + Environment.NewLine),
                Stopwatch.GetTimestamp, Stopwatch.Frequency);
        }

        internal void RecordSeed(int situation, double taus, float windSpeed, float windDirection,
            uint seed1, uint seed2, bool fixedMode)
        {
            if (situation != seeded + 1 || seeded != completed || situation > end ||
                !double.IsFinite(taus) || taus <= 0)
                throw new InvalidOperationException("Benchmark situations must be contiguous from 1 with positive finite TAUS.");
            seeded = situation;
            pendingModelSeconds = taus;
            Write(new { event_type = "seed", IWET = situation, TAUS = taus, WindVelGral = windSpeed,
                WindDirGral = windDirection, Seed1 = seed1, Seed2 = seed2, fixed_mode = fixedMode,
                stopwatch_timestamp = timestamp() });
        }

        internal void CompleteSituation(int situation, Action drainOutputs)
        {
            if (situation != seeded || situation != completed + 1)
                throw new InvalidOperationException("Benchmark completion does not match its seed record.");
            completed = situation;
            modelSeconds += pendingModelSeconds;
            if (situation != warmup && situation != end) return;

            // Only the two measurement boundaries drain async output; intermediate overlap stays intact.
            drainOutputs();
            long now = timestamp();
            if (situation == warmup)
            {
                startTimestamp = now;
                warmupModelSeconds = modelSeconds;
                started = true;
            }
            else
            {
                if (!started) throw new InvalidOperationException("Benchmark warmup boundary was not reached.");
                stopped = true;
            }
            Write(new { event_type = "boundary", boundary = situation == warmup ? "start" : "stop",
                IWET = situation, stopwatch_timestamp = now, stopwatch_frequency = frequency,
                elapsed_s = (now - startTimestamp) / (double)frequency,
                cumulative_model_seconds = modelSeconds, measured_model_seconds = modelSeconds - warmupModelSeconds,
                completed_situations = completed, measured_situations = completed - warmup });
        }

        internal void Finish()
        {
            Write(new { event_type = stopped ? "finished" : "incomplete", complete = stopped,
                requested_end = end, seeded_situations = seeded, completed_situations = completed,
                cumulative_model_seconds = modelSeconds });
        }

        private void Write(object record) => append(JsonSerializer.Serialize(record));
    }
}
