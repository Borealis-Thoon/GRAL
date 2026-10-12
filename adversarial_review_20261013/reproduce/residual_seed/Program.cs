using System.Globalization;
using System.Reflection;
using System.Text.Json;

class SeedChecks
{
    static int checks = 0;
    static readonly List<string> failed = new();
    static MethodInfo residual = null!;
    static FieldInfo situation = null!;
    static ConstructorInfo fixedSeed = null!;
    static PropertyInfo seed1 = null!, seed2 = null!;

    static void Check(bool condition, string name)
    {
        checks++;
        if (!condition) failed.Add(name);
    }

    static (uint, uint) Original(int iw, int i, int j)
    {
        object seed = fixedSeed.Invoke(new object[] { iw, 2.0F, 180.0F });
        return unchecked(((uint)seed1.GetValue(seed)! + (uint)(i + j), (uint)seed2.GetValue(seed)! + (uint)(i * 2)));
    }

    static (uint, uint) Candidate(int i, int j, int k, int sg, int p, uint w, uint z)
    {
        object[] args = { i, j, k, sg, p, w, z };
        residual.Invoke(null, args);
        return ((uint)args[5], (uint)args[6]);
    }

    static uint Mwc(ref uint w, ref uint z)
    {
        unchecked
        {
            z = 36969 * (z & 65535) + (z >> 16);
            w = 18000 * (w & 65535) + (w >> 16);
            return (z << 16) + w;
        }
    }

    static float Uniform(uint raw)
    {
        return unchecked((raw + 1) * 2.328306435454494e-10F);
    }

    static ulong UndoRightXor(ulong value, int shift)
    {
        ulong result = value;
        for (int n = 0; n < 6; n++) result = value ^ (result >> shift);
        return result;
    }

    static ulong Unmix(ulong value)
    {
        unchecked
        {
            value = UndoRightXor(value, 31) * 0x319642B2D24D8EC3UL;
            value = UndoRightXor(value, 27) * 0x96DE1B173F119089UL;
            return UndoRightXor(value, 30) - 0x9E3779B97F4A7C15UL;
        }
    }

    static int Main(string[] args)
    {
        CultureInfo.CurrentCulture = CultureInfo.InvariantCulture;
        string assemblyPath = args[0], outdir = args[1];
        Directory.CreateDirectory(outdir);
        Assembly assembly = Assembly.LoadFrom(assemblyPath);
        Type driver = assembly.GetType("GRAL_2001.ZeitschleifeNonSteadyState", true)!;
        Type program = assembly.GetType("GRAL_2001.Program", true)!;
        Type seedType = program.GetNestedType("DeterministicRandomGenerator", BindingFlags.Public)!;
        fixedSeed = seedType.GetConstructor(new[] { typeof(int), typeof(float), typeof(float) })!;
        seed1 = seedType.GetProperty("Seed1")!;
        seed2 = seedType.GetProperty("Seed2")!;
        situation = program.GetField("IWET", BindingFlags.Public | BindingFlags.Static)!;
        residual = driver.GetMethod("ResidualSeeds", BindingFlags.NonPublic | BindingFlags.Static)!;
        MethodInfo mix = driver.GetMethod("MixSeed", BindingFlags.NonPublic | BindingFlags.Static)!;
        Check(residual != null, "actual compiled private helper present");
        Check((bool)program.GetField("UseFixedRndSeedVal")!.GetValue(null)! == false, "loading assembly does not execute engine main");
        situation.SetValue(null, 7);
        const int I = 15, J = 21, draws = 16384;
        var contexts = new List<object>();
        var oldUnique = new HashSet<(uint, uint)>();
        var newUnique = new HashSet<(uint, uint)>();
        using var writer = new StreamWriter(Path.Combine(outdir, "candidate_rng_draws.csv"));
        writer.WriteLine("context,draw,upstream_raw,candidate_raw,upstream_uniform,candidate_uniform");
        int id = 0;
        foreach (int k in new[] { 1, 2 })
        foreach (int sg in new[] { 0, 1 })
        foreach (int split in new[] { 0, 1, 2 })
        {
            var old = Original(7, I, J);
            var revised = Candidate(I, J, k, sg, split, old.Item1, old.Item2);
            Check(revised == Candidate(I, J, k, sg, split, old.Item1, old.Item2), "fixed repeat context " + id);
            oldUnique.Add(old); newUnique.Add(revised);
            contexts.Add(new { id, situation = 7, i = I, j = J, k, source_group = sg, split, upstream_w = old.Item1, upstream_z = old.Item2, candidate_w = revised.Item1, candidate_z = revised.Item2 });
            uint ow = old.Item1, oz = old.Item2, nw = revised.Item1, nz = revised.Item2;
            for (int n = 0; n < draws; n++)
            {
                uint o = Mwc(ref ow, ref oz), c = Mwc(ref nw, ref nz);
                writer.WriteLine($"{id},{n},{o},{c},{Uniform(o):R},{Uniform(c):R}");
            }
            id++;
        }
        writer.Flush();
        Check(oldUnique.Count == 1, "upstream 12 contexts share exact seed pair");
        Check(newUnique.Count == 12, "candidate 12 contexts have distinct seed pairs");
        var baseSeeds = Original(7, I, J);
        var reference = Candidate(I, J, 1, 0, 0, baseSeeds.Item1, baseSeeds.Item2);
        foreach (var c in new[] { (I+1, J, 1, 0, 0), (I, J+1, 1, 0, 0), (I, J, 2, 0, 0), (I, J, 1, 1, 0), (I, J, 1, 0, 1) })
            Check(reference != Candidate(c.Item1, c.Item2, c.Item3, c.Item4, c.Item5, baseSeeds.Item1, baseSeeds.Item2), "context change " + c);
        situation.SetValue(null, 8);
        Check(reference != Candidate(I, J, 1, 0, 0, baseSeeds.Item1, baseSeeds.Item2), "explicit situation change with same base seed");
        situation.SetValue(null, 7);
        var all = new HashSet<(uint, uint)>();
        for (int k = 1; k <= 20; k++)
        for (int sg = 0; sg < 20; sg++)
        for (int p = 0; p < 50; p++)
            all.Add(Candidate(I, J, k, sg, p, baseSeeds.Item1, baseSeeds.Item2));
        Check(all.Count == 20000, "20000 context seeds collision-free in sampled fixture");
        var parallel = new (uint, uint)[128];
        Parallel.For(0, parallel.Length, n => parallel[n] = Candidate(I, J, 1, 0, 0, baseSeeds.Item1, baseSeeds.Item2));
        Check(parallel.All(value => value == reference), "parallel helper repeatability");
        uint tick = 123456;
        uint rw = unchecked(tick + (uint)(I + J) + 521288629u), rz = unchecked(tick + (uint)(I + J) + 2232121u);
        var randomBase = Candidate(I, J, 1, 0, 0, rw, rz);
        Check(randomBase != Candidate(I, J, 1, 1, 0, rw, rz), "same captured TickCount separates source groups");
        Check(randomBase != Candidate(I, J, 1, 0, 1, rw, rz), "same captured TickCount separates split copies");
        foreach (ulong v in new[] { 0UL, 1UL, 0xFFFFFFFFFFFFFFFFUL, 0x0123456789ABCDEFUL })
            Check(Unmix((ulong)mix.Invoke(null, new object[] { v })!) == v, "inverse mix verification " + v);
        foreach (uint badW in new[] { 0u, 1179647999u, 2359295998u, 3538943997u })
        foreach (uint badZ in new[] { 0u, 2422800383u })
        {
            ulong h = ((ulong)badZ << 32) | badW;
            h = Unmix(h); // splitIndex = 0
            h = Unmix(h) ^ 1UL; // k = 1, SG = 0
            h = Unmix(h) ^ ((ulong)I | ((ulong)J << 32));
            h = Unmix(h) ^ 7UL ^ 0x7265736964UL;
            h = Unmix(h);
            var safe = Candidate(I, J, 1, 0, 0, unchecked((uint)h), (uint)(h >> 32));
            Check(safe.Item1 == 521288629u && safe.Item2 == 2232121u, "zero/fixed point guard " + badW + "/" + badZ);
        }
        File.WriteAllText(Path.Combine(outdir, "candidate_rng_contexts.json"), JsonSerializer.Serialize(new { fixture = "isolated residual MWC seed demonstration; not a GRAL concentration simulation", source = assemblyPath, draws_per_context = draws, contexts, upstream_unique_seed_pairs = oldUnique.Count, candidate_unique_seed_pairs = newUnique.Count, sampled_context_count = 20000, sampled_unique_seed_pairs = all.Count }, new JsonSerializerOptions { WriteIndented = true }));
        var result = new { status = failed.Count == 0 ? "pass" : "fail", checks, errors = failed, engine_main_executed = false, concentration_simulation_run = false, helper = "compiled candidate A private ResidualSeeds via reflection", upstream = "exact fixed-seed expressions replayed with compiled upstream seed constructor" };
        File.WriteAllText(Path.Combine(outdir, "candidate_seed_checks.json"), JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine(JsonSerializer.Serialize(result));
        return failed.Count == 0 ? 0 : 1;
    }
}
