using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json;

if (args.Length != 1) throw new ArgumentException("One GRAL.dll path is required.");
var assembly = AssemblyLoadContext.Default.LoadFromAssemblyPath(Path.GetFullPath(args[0]));
var type = assembly.GetType("GRAL_2001.Program+DeterministicRandomGenerator", true)!;
var seed1 = type.GetProperty("Seed1")!;
var seed2 = type.GetProperty("Seed2")!;
int[] offsets = [0, 100000, 200000, 300000, 400000, 500000];
var states = new List<object>();
var distinct = new HashSet<(uint, uint)>();
foreach (int offset in offsets)
{
    for (int situation = 1; situation <= 48; situation++)
    {
        int seededSituation = checked(situation + offset);
        object instance = Activator.CreateInstance(type, seededSituation, 2f, 0f)!;
        uint first = (uint)seed1.GetValue(instance)!;
        uint second = (uint)seed2.GetValue(instance)!;
        uint expected1 = checked(521288629u + 200u + ((uint)seededSituation << 2));
        uint expected2 = checked(2232121u + ((uint)seededSituation << 1));
        if ((first, second) != (expected1, expected2))
            throw new InvalidOperationException("Actual constructor differs from the independent seed formula.");
        if (situation == 1 && !distinct.Add((first, second)))
            throw new InvalidOperationException("Offsets reuse an actual RNG state.");
        states.Add(new { offset, situation, seed1 = first, seed2 = second });
    }
}
Console.WriteLine(JsonSerializer.Serialize(new
{
    status = "pass",
    scope = "reflection invokes the actual nested RNG constructor; GRAL Main is never invoked",
    offsets,
    states,
    checked_states = states.Count,
    zero_offset_first_seed1 = 521288833u,
    zero_offset_first_seed2 = 2232123u
}));
