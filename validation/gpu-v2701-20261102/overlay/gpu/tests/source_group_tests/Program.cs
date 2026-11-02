using System.Collections;
using System.Globalization;
using System.Reflection;
using System.Text;

CultureInfo.CurrentCulture = CultureInfo.InvariantCulture;
var asm = Assembly.Load("GRAL");
var program = asm.GetType("GRAL_2001.Program", true)!;
var groups = (IList)program.GetField("SourceGroups")!.GetValue(null)!;
var decay = (double[])program.GetField("DecayRate")!.GetValue(null)!;
void Set(string name, object value) { var f = program.GetField(name)!; f.SetValue(null, Convert.ChangeType(value, f.FieldType)); }
void Assert(bool condition, string message) { if (!condition) throw new Exception(message); }
int failures = 0;
void Test(string name, Action action) { try { action(); Console.Error.WriteLine("PASS " + name); } catch (Exception e) { failures++; Console.Error.WriteLine("FAIL " + name + ": " + (e.InnerException ?? e).Message); } }
var dir = Path.Combine(Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location)!, "fixture");
Directory.CreateDirectory(dir);
Directory.SetCurrentDirectory(dir);
if (args.Length == 2 && args[0] == "geometry")
{
    File.WriteAllText("GRAL.geb", "1\n1\n1;1\n10\n10\n1\n" + args[1] + "\n0\n1000\n0\n1000\n");
    Set("WaitForConsoleKey", false);
    var reader = Activator.CreateInstance(asm.GetType("GRAL_2001.ProgramReaders", true)!)!;
    reader.GetType().GetMethod("ReadGRALGeb")!.Invoke(reader, null);
    var expectedGroups = args[1].Split(',').Select(int.Parse).Cast<object>();
    return groups.Cast<object>().SequenceEqual(expectedGroups) ? 0 : 2;
}
foreach (var (sg, expected) in new[]{("0", 0), ("255", 0), ("-1", 1), ("256", 1), (string.Join(",", Enumerable.Range(1, 108)), 0)})
{
    Test("geometry group " + sg, () => {
        var child = new System.Diagnostics.ProcessStartInfo("dotnet") { UseShellExecute = false, RedirectStandardOutput = true, RedirectStandardError = true };
        child.ArgumentList.Add(Assembly.GetExecutingAssembly().Location); child.ArgumentList.Add("geometry"); child.ArgumentList.Add(sg);
        using var p = System.Diagnostics.Process.Start(child)!; p.StandardOutput.ReadToEnd(); p.StandardError.ReadToEnd(); p.WaitForExit();
        Assert(p.ExitCode == expected, $"exit {p.ExitCode}, expected {expected}");
    });
}
groups.Clear(); for (int i = 1; i <= 108; i++) groups.Add(i);
Set("WaitForConsoleKey", false);
foreach (var name in new[]{"XsiMinGral", "EtaMinGral"}) Set(name, 0);
foreach (var name in new[]{"XsiMaxGral", "EtaMaxGral"}) Set(name, 1000);
void Read(string type) => asm.GetType("GRAL_2001." + type, true)!.GetMethod("Read")!.Invoke(null, null);
var specs = new[]{ ("ReadAreaSources", "cadastre.dat", 1), ("ReadPointSources", "point.dat", 2), ("ReadLineSources", "line.dat", 5), ("ReadTunnelPortals", "portals.dat", 2) };
foreach (var (type, file, headers) in specs)
{
    File.WriteAllText(file, string.Concat(Enumerable.Repeat("header\n", headers)));
    Test(type + " 108 group report", () => Read(type));
}
void Pollutant(string text) { File.WriteAllText("Pollutant.txt", text); var r = Activator.CreateInstance(asm.GetType("GRAL_2001.ProgramReaders", true)!)!; r.GetType().GetMethod("ReadPollutantTXT")!.Invoke(r, null); }
Test("decay 108 default zero", () => { Array.Clear(decay); Pollutant("NOx\n0\n0\n0\n"); Assert(decay.Length > 108 && decay[108] == 0, "missing or nonzero group 108"); });
Test("decay default and overrides 1,100,101,108,255", () => { Array.Clear(decay); Pollutant("NOx\n0\n0\n0.25\n1:0.1\t100:0.2\t101:0.3\t108:0.4\t255:0.5\t256:0.9\t-1:0.9\t0:0.9\n"); Assert(decay.Length == 256, "expected 256 byte-indexed entries"); foreach(var (id, expected) in new[]{(0,0.25),(1,0.1),(2,0.25),(100,0.2),(101,0.3),(108,0.4),(255,0.5)}) Assert(Math.Abs(decay[id]-expected)<1e-12, $"group {id}: {decay[id]}, expected {expected}"); });
if (failures == 0)
{
    foreach (var (type, file, headers) in specs)
    {
        var sb = new StringBuilder(string.Concat(Enumerable.Repeat("header\n", headers)));
        foreach (int sg in new[]{1,100,101,108}) sb.AppendLine(type switch {
            "ReadAreaSources" => $"100;100;2;10;10;2;{sg};0;0;0;{sg}",
            "ReadPointSources" => $"100;100;2;{sg};0;0;0;1;1;293;{sg}",
            "ReadLineSources" => $"0;0;{sg};100;100;2;110;100;2;1;1;0;0;{sg}",
            _ => $"100;100;110;100;2;2;{sg};0;0;0;{sg}"
        });
        File.WriteAllText(file, sb.ToString());
        Test(type + " fixture groups 1,100,101,108", () => { var before = Console.Out; using var output = new StringWriter(); Console.SetOut(output); try { Read(type); } finally { Console.SetOut(before); } var s = output.ToString(); foreach (int sg in new[]{1,100,101,108}) Assert(s.Contains($"SG {sg}[kg/h]: "), "missing group " + sg); Assert(s.Contains("Total number of") && s.Contains(": 4"), "expected four sources: " + s); Assert(!s.Contains("SG 108[kg/h]: 0.000"), "group 108 emission missing"); var sgField = type switch { "ReadAreaSources" => "AS_SG", "ReadPointSources" => "PS_SG", "ReadLineSources" => "LS_SG", _ => "TS_SG" }; var actual = (byte[])program.GetField(sgField)!.GetValue(null)!; Assert(actual.Skip(1).Take(4).SequenceEqual(new byte[]{1,100,101,108}), sgField + " values changed"); });
    }
}
return failures == 0 ? 0 : 1;




