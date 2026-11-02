using System.Collections;
using System.Collections.Frozen;
using System.Reflection;
using System.Text.Json;
using System.Diagnostics;
using System.Security.Cryptography;

internal static partial class HostContracts
{
    private static readonly Assembly Model = Assembly.Load("GRAL");
    private static readonly Type Program = Model.GetType("GRAL_2001.Program", true)!;
    private static readonly List<object> Results = new();
    private static void Set(string name, object value) => Program.GetField(name)!.SetValue(null, value);
    private static object Get(string name) => Program.GetField(name)!.GetValue(null)!;
    private static object Call(string type, string method, params object[] args)
    {
        var t = Model.GetType("GRAL_2001." + type);
        if (t == null) throw new Exception("Missing GPU host type " + type);
        var target = t.GetMethod(method, BindingFlags.Static | BindingFlags.NonPublic) ?? throw new Exception("Missing host method " + type + "." + method);
        try { return target.Invoke(null, args)!; }
        catch (TargetInvocationException e) { throw e.InnerException!; }
    }
    private static void Check(bool condition, string message) { if (!condition) throw new Exception(message); }
    private static void Reject(Action run, string contains)
    {
        try { run(); }
        catch (Exception e) when (e.Message.Contains(contains, StringComparison.OrdinalIgnoreCase)) { return; }
        throw new Exception("Expected rejection: " + contains);
    }
    private static void Test(string name, Action run)
    {
        try { run(); Results.Add(new { name, status = "pass" }); Console.WriteLine("PASS " + name); }
        catch (Exception e) { Results.Add(new { name, status = "fail", error = e.Message }); Console.WriteLine("FAIL " + name + ": " + e.Message); }
    }
    private static List<Dictionary<string, object>> Batches(int capacity)
        => ((IEnumerable<Dictionary<string, object>>)Call("GpuResidualBatch", "Enumerate", capacity)).ToList();
    private static void ResidualSetup()
    {
        Set("UseFixedRndSeedVal", true); Set("SourceType", new byte[2]);
        Set("NII", 2); Set("NJJ", 2); Set("NKK_Transient", 2);
        var groups = (List<int>)Get("SourceGroups"); groups.Clear(); groups.AddRange(new[] { 17, 3 });
        Set("DXK", 2f); Set("DYK", 3f); Set("DZK_Trans", new[] { 0f, 2f, 4f });
        Set("GridVolume", 12f); Set("TAUS", 2f); Set("ParticleMassMean", 1d); Set("TransConcThreshold", 0.5f);
        var grid = new float[3][][][];
        for (int i = 0; i < 3; i++) { grid[i] = new float[3][][]; for (int j = 0; j < 3; j++) { grid[i][j] = new float[3][]; for (int k = 0; k < 3; k++) grid[i][j][k] = new float[2]; } }
        grid[1][1][2][0] = 20f; // volume ratio 2, mass 20 -> three split particles
        grid[1][1][1][1] = 0.5f; // threshold equality, one particle
        grid[2][1][2][1] = float.NaN;
        grid[2][2][1][0] = 40f; // ratio 1, mass 20 -> three split particles
        Set("Conz4d", grid);
    }
    private static void GuardSetup()
    {
        Set("ISTATIONAER", 0); Set("Topo", 1); Set("IStatistics", 4); Set("UseFixedRndSeedVal", true);
        foreach (string flag in new[] { "BuildingsExist", "WetDeposition", "DepositionExist", "Odour", "WriteVerticalConcentration", "TunnelEntr", "TunnelOppLane" }) Set(flag, false);
        Set("AdaptiveRoughnessMax", 0f); Set("LogLevel", 0); Set("PS_Count", 0); Set("LS_Count", 0); Set("TS_Count", 0);
        Set("AS_Count", 1); Set("AS_Mode", new byte[2]); Set("SourceType", new byte[] { 0, 3 });
        Set("ParticleMode", new byte[2]); Set("NS", 1); Set("ReceptorNumber", 0); Set("ReceptorNearbyBuilding", new bool[1]);
        Array.Clear((double[])Get("DecayRate"));
    }
    private static MemoryStream Export(string[] fields, IReadOnlyDictionary<string, object>? extra = null)
    {
        var stream = new MemoryStream();
        Call("GpuFieldExport", "Export", stream, fields, "init", null!, null!, null!, extra!, null!, null!);
        stream.Position = 0; return stream;
    }
    private static JsonDocument Header(MemoryStream stream)
    {
        using var r = new BinaryReader(stream, System.Text.Encoding.UTF8, true);
        return JsonDocument.Parse(r.ReadBytes(checked((int)r.ReadUInt64())));
    }
    private static bool Alive(int pid)
    { try { using var process = Process.GetProcessById(pid); return !process.HasExited; } catch (ArgumentException) { return false; } }
    private static void StopTestProcess(int pid)
    { if (!Alive(pid)) return; using var process = Process.GetProcessById(pid); process.Kill(entireProcessTree: true); process.WaitForExit(5000); }
    private static (IDisposable connection, int pid) Connection(string script, string log)
    {
        string python = Environment.GetEnvironmentVariable("HOST_TEST_PYTHON") ?? "python3";
        var type = Model.GetType("GRAL_2001.GpuServerConnection", true)!;
        var connection = (IDisposable)Activator.CreateInstance(type, BindingFlags.Instance | BindingFlags.NonPublic, null, new object[] { python, script, log }, null)!;
        var process = (Process)type.GetField("process", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(connection)!;
        return (connection, process.Id);
    }
    private static MemoryStream SerializationFrame()
    {
        var dense = new double[64][][][];
        for (int i = 0; i < dense.Length; i++)
        {
            dense[i] = new double[64][][];
            for (int j = 0; j < dense[i].Length; j++)
            {
                dense[i][j] = new double[2][];
                for (int k = 0; k < 2; k++) dense[i][j][k] = Enumerable.Range(0, 4).Select(sg => (double)(i * 1024 + j * 16 + k * 4 + sg)).ToArray();
            }
        }
        return Export(Array.Empty<string>(), new Dictionary<string, object> { ["dense"] = dense, ["ragged"] = new float[][] { new[] { 1f, 2f, 3f }, null!, new[] { 4f } } });
    }
    private static int SerializationBenchmark(string output)
    {
        using (var warmup = SerializationFrame()) { }
        var samples = new List<object>(); var hashes = new HashSet<string>();
        for (int n = 0; n < 3; n++)
        {
            long allocated = GC.GetAllocatedBytesForCurrentThread(); var clock = Stopwatch.StartNew();
            using var frame = SerializationFrame(); clock.Stop(); allocated = GC.GetAllocatedBytesForCurrentThread() - allocated;
            string sha = Convert.ToHexString(SHA256.HashData(frame.ToArray())).ToLowerInvariant(); hashes.Add(sha);
            samples.Add(new { iteration = n, elapsed_ms = clock.Elapsed.TotalMilliseconds, allocated_bytes = allocated, frame_bytes = frame.Length, sha256 = sha });
        }
        File.WriteAllText(output, JsonSerializer.Serialize(new { status = hashes.Count == 1 ? "pass" : "fail", utc = DateTimeOffset.UtcNow, fixture = "dense-double-64x64x2x4-plus-ragged-float", samples }, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine("SERIALIZATION " + string.Join(",", hashes));
        return hashes.Count == 1 ? 0 : 1;
    }
    private sealed class CountingStream : MemoryStream
    {
        internal int Writes;
        public override void Write(byte[] buffer, int offset, int count) { Writes++; base.Write(buffer, offset, count); }
        public override void Write(ReadOnlySpan<byte> buffer) { Writes++; base.Write(buffer); }
    }
    private static (byte[] bytes, int calls, double ms) CountFrame(bool buffered)
    {
        var leaves = new double[3000][];
        for (int i = 0; i < leaves.Length; i++) { leaves[i] = new double[36]; leaves[i][0] = i + 0.25; }
        using var raw = new CountingStream(); using Stream target = buffered ? new BufferedStream(raw, 1024 * 1024) : raw;
        var timer = Stopwatch.StartNew();
        Call("GpuFieldExport", "Export", target, Array.Empty<string>(), "init", null!, null!, null!, new Dictionary<string, object> { ["leaves"] = leaves }, null!, null!);
        timer.Stop(); return (raw.ToArray(), raw.Writes, timer.Elapsed.TotalMilliseconds);
    }
    private static int BufferedBenchmark(string output)
    {
        var samples = new List<object>();
        foreach (bool buffered in new[] { false, true })
        {
            CountFrame(buffered);
            for (int i = 0; i < 3; i++)
            {
                var frame = CountFrame(buffered);
                samples.Add(new { buffered, repeat = i, frame_bytes = frame.bytes.Length, writes = frame.calls, elapsed_ms = frame.ms, sha256 = Convert.ToHexString(SHA256.HashData(frame.bytes)).ToLowerInvariant() });
            }
        }
        File.WriteAllText(output, JsonSerializer.Serialize(new { fixture = "3000_288byte_leaves", samples }, new JsonSerializerOptions { WriteIndented = true })); return 0;
    }
    private static int PaddingBenchmark(string output)
    {
        var method = Model.GetType("GRAL_2001.GpuFieldExport", true)!.GetMethod("WriteZeros", BindingFlags.Static | BindingFlags.NonPublic)!;
        var write = method.CreateDelegate<Action<BinaryWriter, long, byte[]>>();
        using var stream = new MemoryStream(1024); using var writer = new BinaryWriter(stream); var scratch = new byte[1024 * 1024];
        const int iterations = 30000; var samples = new List<object>();
        foreach (int bytes in new[] { 1, 288 })
        {
            for (int i = 0; i < 500; i++) { stream.Position = 0; write(writer, bytes, scratch); }
            for (int repeat = 0; repeat < 3; repeat++)
            {
                var clock = Stopwatch.StartNew();
                for (int i = 0; i < iterations; i++) { stream.Position = 0; write(writer, bytes, scratch); }
                samples.Add(new { bytes, repeat, iterations, elapsed_ms = clock.Elapsed.TotalMilliseconds });
            }
        }
        File.WriteAllText(output, JsonSerializer.Serialize(new { fixture = "zero-initialized-reused-scratch-memory-stream", scratch_bytes = scratch.Length, samples }, new JsonSerializerOptions { WriteIndented = true }));
        return 0;
    }
    public static int Main(string[] args)
    {
        if (args.Length == 2 && args[0] == "--serialization-bench") return SerializationBenchmark(args[1]);
        if (args.Length == 2 && args[0] == "--padding-bench") return PaddingBenchmark(args[1]);
        if (args.Length == 2 && args[0] == "--buffered-bench") return BufferedBenchmark(args[1]);
        Test("init_cache_export_reconstructs_and_invalidates_changed_contents", () =>
        {
            string[] cached = { "ParticleMass", "ParticleSG", "ParticleSource", "SourceType", "ParticleMode", "ParticleVdep", "ParticleVsed" };
            string[] xyz = { "Xcoord", "YCoord", "ZCoord" }; string[] names = cached.Concat(xyz).ToArray();
            Set("ParticleMass", new[] { 1d, 2d }); Set("ParticleSG", new byte[] { 3, 4 }); Set("ParticleSource", new[] { 5, 6 });
            Set("SourceType", new byte[] { 7, 8 }); Set("ParticleMode", new byte[] { 9, 10 });
            Set("ParticleVdep", new[] { 11f, 12f }); Set("ParticleVsed", new[] { 13f, 14f });
            Set("Xcoord", new[] { 15d, 16d }); Set("YCoord", new[] { 17d, 18d }); Set("ZCoord", new[] { 19f, 20f });
            var type = Model.GetType("GRAL_2001.GpuInputCache");
            Check(type != null, "GPU input cache is missing");
            object cache = Activator.CreateInstance(type!, true)!;
            object Prepare() => type!.GetMethod("Prepare", BindingFlags.Instance | BindingFlags.NonPublic)!.Invoke(cache, new object[] { names })!;
            string[] Fields(object plan) => ((IEnumerable<string>)plan.GetType().GetProperty("Fields", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(plan)!).ToArray();
            void Commit(object plan, long payload) { using var ack = JsonDocument.Parse("{\"payload_bytes\":" + payload + "}"); try { plan.GetType().GetMethod("Commit", BindingFlags.Instance | BindingFlags.NonPublic)!.Invoke(plan, new object[] { ack.RootElement }); } catch (TargetInvocationException e) { throw e.InnerException!; } }
            Dictionary<string, (string descriptor, byte[] data)> Read(object plan)
            {
                using var stream = Export(Fields(plan)); using var header = Header(stream); long payloadStart = stream.Position;
                var result = new Dictionary<string, (string, byte[])>();
                foreach (var a in header.RootElement.GetProperty("arrays").EnumerateArray())
                {
                    stream.Position = payloadStart + a.GetProperty("offset").GetInt64(); var bytes = new byte[a.GetProperty("bytes").GetInt32()]; stream.ReadExactly(bytes);
                    result.Add(a.GetProperty("name").GetString()!, (a.GetProperty("dtype").ToString() + ":" + a.GetProperty("shape").ToString() + ":" + a.GetProperty("is_null").ToString(), bytes));
                }
                return result;
            }
            var first = Prepare(); Check(Fields(first).Length == names.Length, "First init omitted fields"); var state = Read(first);
            Reject(() => Commit(first, 1), "payload"); Check(Fields(Prepare()).Length == names.Length, "Failed acknowledgement committed snapshot");
            Commit(first, 0);
            foreach (string name in cached) Set(name, ((Array)Get(name)).Clone());
            var second = Prepare(); Check(Fields(second).SequenceEqual(xyz), "Equal new arrays or position scope incorrect");
            Check((long)second.GetType().GetProperty("SavedPayloadBytes", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(second)! == 46, "Saved payload byte count differs");
            Check(((IEnumerable<string>)second.GetType().GetProperty("Omitted", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(second)!).SequenceEqual(cached), "Omitted names differ");
            foreach (var pair in Read(second)) state[pair.Key] = pair.Value;
            var fullCache = Activator.CreateInstance(type!, true)!;
            object fullPlan = type!.GetMethod("Prepare", BindingFlags.Instance | BindingFlags.NonPublic)!.Invoke(fullCache, new object[] { names })!;
            var expected = Read(fullPlan);
            Check(expected.All(p => state[p.Key].descriptor == p.Value.descriptor && state[p.Key].data.SequenceEqual(p.Value.data)), "Reconstructed server state differs");
            Commit(second, 0);
            ((double[])Get("ParticleMass"))[0] = 99;
            var rejected = Prepare(); Reject(() => Commit(rejected, 1), "payload");
            Check(Fields(Prepare()).Contains("ParticleMass"), "Failed acknowledgement advanced existing snapshot");
            ((double[])Get("ParticleMass"))[0] = 1;
            Check(!Fields(Prepare()).Contains("ParticleMass"), "Failed acknowledgement overwrote prior successful snapshot");
            foreach (string name in cached)
            {
                Array value = (Array)Get(name); object original = value.GetValue(0)!;
                if (value is double[] d) d[0] += 1; else if (value is float[] f) f[0] += 1; else if (value is int[] i) i[0] += 1; else ((byte[])value)[0]++;
                var changed = Prepare(); Check(Fields(changed).Contains(name), "In-place change omitted: " + name); Commit(changed, 0); value.SetValue(original, 0);
                changed = Prepare(); Check(Fields(changed).Contains(name), "Restored contents omitted: " + name); Commit(changed, 0);
                Set(name, Array.CreateInstance(value.GetType().GetElementType()!, 3));
                changed = Prepare(); Check(Fields(changed).Contains(name), "Changed length omitted: " + name); Commit(changed, 0);
                Set(name, null!); changed = Prepare(); Check(Fields(changed).Contains(name), "Null omitted: " + name); Commit(changed, 0);
                Set(name, Array.CreateInstance(value.GetType().GetElementType()!, 0)); changed = Prepare(); Check(Fields(changed).Contains(name), "Null to empty omitted: " + name); Commit(changed, 0);
                Set(name, value); changed = Prepare(); Commit(changed, 0);
            }
        });
        Test("residual_split_order_threshold_and_batch_boundary", () =>
        {
            ResidualSetup(); var batches = Batches(2); Check(batches.Count == 4, "Expected four batches");
            var rows = batches.SelectMany(b => Enumerable.Range(0, ((int[])b["_resI"]).Length).Select(q => (
                i: ((int[])b["_resI"])[q], j: ((int[])b["_resJ"])[q], k: ((int[])b["_resK"])[q],
                sg: ((int[])b["_resSG"])[q], split: ((int[])b["_resSplit"])[q], conc: ((float[])b["_resConc"])[q]))).ToArray();
            Check(rows.Length == 7, "Split count must count subparticles, not occupied cells");
            Check(rows[0] == (1, 1, 2, 0, 0, 20f / 3), "First residual row differs");
            Check(rows[2] == (1, 1, 2, 0, 2, 20f / 3), "Split indices reset across batch boundary");
            Check(rows[3] == (1, 1, 1, 1, 0, 0.5f), "Threshold equality or descending-k order differs");
            Check(rows[6] == (2, 2, 1, 0, 2, 40f / 3), "Cell/SG order differs");
        });
        Test("residual_split_cap_100000", () =>
        {
            ResidualSetup(); var grid = (float[][][][])Get("Conz4d");
            foreach (var a in grid) foreach (var b in a) foreach (var c in b) Array.Clear(c);
            grid[1][1][2][0] = 2_000_000f;
            var batches = Batches(65_536); Check(batches.Count == 2, "Expected two capped batches");
            Check(batches.Sum(b => ((int[])b["_resI"]).Length) == 100_000, "Cap differs from V2701");
            Check(((int[])batches[1]["_resSplit"])[^1] == 99_999, "Final split index differs");
        });
        Test("csr_boundary_cells_and_dictionary_list_order", () =>
        {
            Set("NXL", 2); Set("NYL", 3);
            Set("GridCellReceptors", new Dictionary<(int, int), List<int>> { [(2, 3)] = new() { 4, 1 }, [(0, 0)] = new() { 3 }, [(1, 2)] = new() { 2, 5 } }.ToFrozenDictionary());
            var extra = (Dictionary<string, object>)Call("GpuSituationDriver", "ReceptorCsr");
            Check((int)extra["GridRecRow"] == 4, "Wrong CSR row stride");
            var start = (int[])extra["GridRecStart"]; var list = (int[])extra["GridRecList"];
            Check(start.Length == 13 && start[0] == 0 && start[1] == 1 && start[6] == 1 && start[7] == 3 && start[11] == 3 && start[12] == 5, "Wrong CSR cell boundaries");
            Check(list.SequenceEqual(new[] { 3, 2, 5, 4, 1 }), "Per-cell dictionary list order changed");
            Set("GridCellReceptors", null!); extra = (Dictionary<string, object>)Call("GpuSituationDriver", "ReceptorCsr");
            Check((int)extra["GridRecRow"] == 0 && ((int[])extra["GridRecStart"]).Length == 0 && ((int[])extra["GridRecList"]).Length == 0, "Null CSR contract differs");
        });
        Test("unsupported_configuration_rejected_before_server_launch", () =>
        {
            GuardSetup(); Call("GpuSituationDriver", "Guard", 1, 1);
            foreach (string name in new[] { "BuildingsExist", "WetDeposition", "DepositionExist", "Odour", "WriteVerticalConcentration", "TunnelEntr", "TunnelOppLane" })
            { Set(name, true); Reject(() => Call("GpuExperimental", "Run", 1, 1), "Unsupported"); Set(name, false); }
            Set("NS", 10); Reject(() => Call("GpuExperimental", "Run", 1, 1), "Unsupported"); Set("NS", 1);
            Set("ReceptorNearbyBuilding", new[] { false, true }); Reject(() => Call("GpuExperimental", "Run", 1, 1), "Unsupported");
        });
        Test("particle_range_and_source_rejections", () =>
        {
            GuardSetup(); Reject(() => Call("GpuSituationDriver", "Guard", 0, 1), "range"); Reject(() => Call("GpuSituationDriver", "Guard", 1, 2), "range");
            Set("SourceType", new byte[] { 0, 1 }); Reject(() => Call("GpuSituationDriver", "Guard", 1, 1), "non-area");
            GuardSetup(); Set("UseFixedRndSeedVal", false); Reject(() => Call("GpuSituationDriver", "Guard", 1, 1), "Unsupported");
        });
        Test("unsupported_numeric_modes_decay_and_stack_limits", () =>
        {
            foreach (var change in new (string name, object value)[] { ("ISTATIONAER", 1), ("Topo", 0), ("IStatistics", 0), ("LogLevel", 1), ("PS_Count", 1), ("LS_Count", 1), ("TS_Count", 1), ("NS", 10), ("ReceptorNumber", 51), ("AdaptiveRoughnessMax", 1f) })
            { GuardSetup(); Set(change.name, change.value); Reject(() => Call("GpuExperimental", "Run", 1, 1), "Unsupported"); }
            GuardSetup(); ((double[])Get("DecayRate"))[17] = 0.1; Reject(() => Call("GpuExperimental", "Run", 1, 1), "Unsupported");
            GuardSetup(); ((byte[])Get("AS_Mode"))[1] = 1; Reject(() => Call("GpuExperimental", "Run", 1, 1), "Unsupported");
            GuardSetup(); ((byte[])Get("ParticleMode"))[1] = 1; Reject(() => Call("GpuExperimental", "Run", 1, 1), "Unsupported");
        });
        Test("export_jagged_padding_rectangular_dtype_and_uint_seed", () =>
        {
            var extra = new Dictionary<string, object> { ["jagged"] = new double[][] { new[] { 1d, 2d }, null!, new[] { 3d } }, ["rect"] = new int[,] { { 4, 5 }, { 6, 7 } }, ["RnGSeed1"] = uint.MaxValue };
            using var stream = Export(Array.Empty<string>(), extra); using var header = Header(stream);
            var arrays = header.RootElement.GetProperty("arrays");
            Check(arrays[0].GetProperty("shape").ToString() == "[3,2]", "Unexpected jagged shape");
            Check(arrays[0].GetProperty("dtype").GetString() == "Double", "Double dtype lost");
            Check(header.RootElement.GetProperty("scalars").GetProperty("RnGSeed1").GetUInt32() == uint.MaxValue, "UInt32 seed changed");
            using var r = new BinaryReader(stream); Check(Enumerable.Range(0, 6).Select(_ => r.ReadDouble()).SequenceEqual(new[] { 1d, 2d, 0d, 0d, 3d, 0d }), "Jagged padding differs");
            Check(Enumerable.Range(0, 4).Select(_ => r.ReadInt32()).SequenceEqual(new[] { 4, 5, 6, 7 }), "Rectangular layout differs");
        });
        Test("import_conz3d_double_without_float_rounding", () =>
        {
            Set("Conz3dDouble", new[] { new[] { new[] { new[] { 1.0000000000000002d } } } });
            using var stream = Export(new[] { "Conz3dDouble" }); using var header = Header(stream);
            Set("Conz3dDouble", new[] { new[] { new[] { new double[1] } } });
            Call("GpuFieldImport", "Apply", stream, header.RootElement);
            Check(((double[][][][])Get("Conz3dDouble"))[0][0][0][0] == 1.0000000000000002d, "Conz3dDouble was rounded");
        });
        Test("import_rejects_unexpected_scalars", () =>
        {
            using var header = JsonDocument.Parse("{\"arrays\":[],\"payload_bytes\":0,\"scalars\":{\"INU_NaNParticles\":1}}");
            Reject(() => Call("GpuFieldImport", "Apply", new MemoryStream(), header.RootElement), "Unexpected result scalar");
        });
        Test("import_rejects_trace_shape_byte_mismatch", () =>
        {
            string target = Path.Combine(Path.GetTempPath(), "gral-trace-contract-" + Guid.NewGuid() + ".bin");
            Environment.SetEnvironmentVariable("INU_GPU_DEVICE_RESIDUAL_TRACE", target);
            try
            {
                using var header = JsonDocument.Parse("{\"arrays\":[{\"name\":\"ResidualTrace\",\"dtype\":\"Double\",\"shape\":[1,16],\"offset\":0,\"bytes\":8}],\"payload_bytes\":8,\"scalars\":{}}");
                Reject(() => Call("GpuFieldImport", "Apply", new MemoryStream(new byte[8]), header.RootElement), "Invalid GPU trace");
            }
            finally { Environment.SetEnvironmentVariable("INU_GPU_DEVICE_RESIDUAL_TRACE", null); if (File.Exists(target)) File.Delete(target); }
        });
        Test("active_fresh_count_uses_assigned_source_and_positive_mass", () =>
        {
            Set("EmissionTimeseriesExist", false);
            Set("ParticleSource", new[] { 0, 1, 0, 2, 3 }); Set("ParticleMass", new[] { 0d, 1d, 9d, 0d, 2d });
            Check((long)Call("GpuSituationDriver", "ActiveFreshCount", 1, 4) == 2, "Inactive or zero-mass fresh slots counted as active");
        });
        Test("active_fresh_count_modulates_mass_using_internal_source_group", () =>
        {
            Set("ISTATIONAER", 0); Set("EmissionTimeseriesExist", true); Set("IWET", 1);
            var groups = (List<int>)Get("SourceGroups"); groups.Clear(); groups.AddRange(new[] { 17, 3 });
            Set("ParticleSource", new[] { 0, 1, 2, 0, 3, 4 });
            Set("ParticleSG", new byte[] { 0, 17, 3, 17, 3, 17 });
            Set("ParticleMass", new[] { 0d, 2d, 2d, 9d, 0d, -2d });
            Set("EmFacTimeSeries", new float[,] { { 0f, 0.5f }, { 1f, 0f } });
            Check((long)Call("GpuSituationDriver", "ActiveFreshCount", 1, 5) == 1, "Time-series zero mass or external-to-internal SG mapping differs");
            Set("EmissionTimeseriesExist", false);
        });
        Test("active_fresh_count_preserves_upstream_last_iwet_guard", () =>
        {
            Set("ISTATIONAER", 0); Set("EmissionTimeseriesExist", true);
            var groups = (List<int>)Get("SourceGroups"); groups.Clear(); groups.Add(17);
            Set("ParticleSource", new[] { 0, 1 }); Set("ParticleSG", new byte[] { 0, 17 }); Set("ParticleMass", new[] { 0d, 2d });
            Set("EmFacTimeSeries", new float[,] { { 0f }, { 0f }, { 0f } });
            Set("IWET", 2);
            Check((long)Call("GpuSituationDriver", "ActiveFreshCount", 1, 1) == 0, "Applicable last guarded row was not modulated");
            Set("IWET", 3);
            Check((long)Call("GpuSituationDriver", "ActiveFreshCount", 1, 1) == 1, "Upstream <= GetUpperBound guard changed at last IWET");
            Set("EmissionTimeseriesExist", false);
        });
        Test("active_fresh_count_rejects_nonfinite_modulated_mass", () =>
        {
            Set("ISTATIONAER", 0); Set("EmissionTimeseriesExist", true); Set("IWET", 1);
            var groups = (List<int>)Get("SourceGroups"); groups.Clear(); groups.Add(17);
            Set("ParticleSource", new[] { 0, 1 }); Set("ParticleSG", new byte[] { 0, 17 }); Set("ParticleMass", new[] { 0d, 2d });
            foreach (float factor in new[] { float.NaN, float.PositiveInfinity, float.NegativeInfinity })
            {
                Set("EmFacTimeSeries", new float[,] { { factor }, { 1f } });
                Reject(() => Call("GpuSituationDriver", "ActiveFreshCount", 1, 1), "non-finite");
            }
            Set("EmissionTimeseriesExist", false); Set("ParticleMass", new[] { 0d, double.NaN });
            Reject(() => Call("GpuSituationDriver", "ActiveFreshCount", 1, 1), "non-finite");
        });
        Test("trace_target_situation_gate", () =>
        {
            Environment.SetEnvironmentVariable("INU_GPU_TRACE_SITUATION", "2");
            try
            {
                Set("IWET", 1); Check(!(bool)Call("GpuSituationDriver", "TraceThisSituation"), "Trace enabled before target situation");
                Set("IWET", 2); Check((bool)Call("GpuSituationDriver", "TraceThisSituation"), "Trace disabled at target situation");
            }
            finally { Environment.SetEnvironmentVariable("INU_GPU_TRACE_SITUATION", null); }
        });
        Test("padding_writes_exact_bytes_between_primitive_payloads", () =>
        {
            const int length = 1024 * 1024;
            foreach (int count in new[] { 0, 1, 7, 288, length, length + 17 })
            {
                using var stream = new MemoryStream(); using var writer = new BinaryWriter(stream);
                var scratch = Enumerable.Repeat((byte)0xA5, length).ToArray();
                writer.Write(0x12345678); Call("GpuFieldExport", "WriteZeros", writer, (long)count, scratch); writer.Write(0x76543210);
                byte[] actual = stream.ToArray(); var expected = new byte[count + 8];
                BitConverter.GetBytes(0x12345678).CopyTo(expected, 0); BitConverter.GetBytes(0x76543210).CopyTo(expected, count + 4);
                Check(actual.SequenceEqual(expected), "Padding frame changed at " + count);
                Check(SHA256.HashData(actual).SequenceEqual(SHA256.HashData(expected)), "Padding frame hash changed at " + count);
            }
        });
        Test("positive_padding_clears_only_bytes_needed", () =>
        {
            const int length = 1024 * 1024;
            foreach (int count in new[] { 0, 1, 7, 288, length, length + 17 })
            {
                using var stream = new MemoryStream(); using var writer = new BinaryWriter(stream);
                var scratch = Enumerable.Repeat((byte)0xA5, length).ToArray();
                Call("GpuFieldExport", "WriteZeros", writer, (long)count, scratch);
                int cleared = Math.Min(count, length);
                Check(scratch.Take(cleared).All(x => x == 0) && scratch.Skip(cleared).All(x => x == 0xA5), "Unexpected scratch mutation at " + count);
            }
        });
        Test("zero_byte_padding_does_not_touch_scratch_buffer", () =>
        {
            using var output = new MemoryStream(); using var writer = new BinaryWriter(output);
            byte[] scratch = Enumerable.Repeat((byte)0xA5, 1024).ToArray();
            Call("GpuFieldExport", "WriteZeros", writer, 0L, scratch);
            Check(output.Length == 0 && scratch.All(value => value == 0xA5), "Zero-byte padding clears scratch storage");
        });
        Test("serialization_wire_bytes_match_preoptimization_fixture", () =>
        {
            using var frame = SerializationFrame();
            Check(Convert.ToHexString(SHA256.HashData(frame.ToArray())).ToLowerInvariant() == "fa40cf3ee9d7d8a6286d748f6b2b5e51914759ff757579bccee0c091a3bfdca2", "Serialized frame changed after zero-padding optimization");
        });
        Test("buffered_export_wire_equals_raw_with_fewer_writes", () =>
        {
            var raw = CountFrame(false); var buffered = CountFrame(true);
            Check(raw.bytes.SequenceEqual(buffered.bytes), "Buffered frame differs from raw wire bytes");
            Check(SHA256.HashData(raw.bytes).SequenceEqual(SHA256.HashData(buffered.bytes)), "Buffered frame SHA differs");
            Check(buffered.calls < raw.calls / 10, "Buffer failed to batch raw writes");
        });
        Test("server_init_and_control_flush_distinct_frames", () =>
        {
            string directory = Path.Combine(Path.GetTempPath(), "gral-buffer-protocol-" + Guid.NewGuid()); Directory.CreateDirectory(directory);
            string script = Path.Combine(directory, "frames.py"), log = Path.Combine(directory, "stderr.log");
            File.WriteAllText(script, "import json,struct,sys\nr=sys.stdin.buffer; w=sys.stdout.buffer\nfor expected in ['init','init','close']:\n n=struct.unpack('<Q',r.read(8))[0]; h=json.loads(r.read(n)); data=r.read(h['payload_bytes'])\n if h['command']!=expected or len(data)!=h['payload_bytes']: sys.exit(3)\n a=json.dumps({'status':'ok','payload_bytes':0,'command':expected}).encode(); w.write(struct.pack('<Q',len(a))+a); w.flush()\n");
            var (connection, pid) = Connection(script, log);
            try
            {
                var type = connection.GetType();
                Check(type.GetField("input", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(connection) is BufferedStream, "Server input is not buffered");
                var init = type.GetMethod("Init", BindingFlags.Instance | BindingFlags.NonPublic)!;
                var read = type.GetMethod("ReadHeader", BindingFlags.Instance | BindingFlags.NonPublic)!;
                Set("Xcoord", new[] { 1d, 2d });
                for (int i = 0; i < 2; i++)
                {
                    init.Invoke(connection, new object?[] { new[] { "Xcoord" }, null });
                    using var ack = (JsonDocument)read.Invoke(connection, null)!; Check(ack.RootElement.GetProperty("command").GetString() == "init", "Init frame boundary lost");
                }
                type.GetMethod("SendControl", BindingFlags.Instance | BindingFlags.NonPublic)!.Invoke(connection, new object?[] { "close", null });
                using var close = (JsonDocument)read.Invoke(connection, null)!; Check(close.RootElement.GetProperty("command").GetString() == "close", "Control frame boundary lost");
                connection.Dispose(); Check(!Alive(pid), "Fixture server survived close");
            }
            finally { StopTestProcess(pid); try { connection.Dispose(); } catch { } foreach (string file in Directory.GetFiles(directory)) File.Delete(file); Directory.Delete(directory); }
        });
        Test("server_buffered_output_reuses_read_ahead_across_payload_and_next_header", () =>
        {
            string directory = Path.Combine(Path.GetTempPath(), "gral-receive-" + Guid.NewGuid()); Directory.CreateDirectory(directory);
            string script = Path.Combine(directory, "frames.py"), log = Path.Combine(directory, "stderr.log");
            File.WriteAllText(script, "import json,struct,sys\nw=sys.stdout.buffer\ndef frame(h,p=b''):\n b=json.dumps(h).encode(); return struct.pack('<Q',len(b))+b+p\na={'status':'ok','arrays':[{'name':'Xcoord','dtype':'Double','shape':[2],'offset':0,'bytes':16}],'payload_bytes':16}\nb={'status':'ok','arrays':[],'payload_bytes':0}\nw.write(frame(a,struct.pack('<dd',1.25,-2.5))+frame(b)); w.flush()\n");
            var (connection, pid) = Connection(script, log); object old = Get("Xcoord");
            try
            {
                var type = connection.GetType();
                var output = type.GetField("output", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(connection) as BufferedStream;
                Check(output != null, "Server output is not buffered");
                var process = (Process)type.GetField("process", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(connection)!;
                Check(process.WaitForExit(5000), "Fixture did not finish writing frames");
                var read = type.GetMethod("ReadHeader", BindingFlags.Instance | BindingFlags.NonPublic)!;
                var apply = type.GetMethod("ApplyResult", BindingFlags.Instance | BindingFlags.NonPublic)!;
                Set("Xcoord", new double[2]);
                using (var first = (JsonDocument)read.Invoke(connection, null)!)
                {
                    var flags = BindingFlags.Instance | BindingFlags.NonPublic;
                    int pos = (int)typeof(BufferedStream).GetField("_readPos", flags)!.GetValue(output)!;
                    int len = (int)typeof(BufferedStream).GetField("_readLen", flags)!.GetValue(output)!;
                    Check(len > pos, "Fixture did not read ahead into payload");
                    apply.Invoke(connection, new object[] { first });
                }
                Check(((double[])Get("Xcoord")).SequenceEqual(new[] { 1.25, -2.5 }), "Payload bytes lost between frames");
                using var second = (JsonDocument)read.Invoke(connection, null)!;
                apply.Invoke(connection, new object[] { second });
                connection.Dispose();
            }
            finally { Set("Xcoord", old); StopTestProcess(pid); try { connection.Dispose(); } catch { } foreach (string file in Directory.GetFiles(directory)) File.Delete(file); Directory.Delete(directory); }
        });
        Test("cancellation_with_pending_buffer_unblocks_dispose", () =>
        {
            string directory = Path.Combine(Path.GetTempPath(), "gral-buffer-cancel-" + Guid.NewGuid()); Directory.CreateDirectory(directory);
            string script = Path.Combine(directory, "stall.py"), log = Path.Combine(directory, "stderr.log"); File.WriteAllText(script, "import time\ntime.sleep(60)\n");
            using var cancellation = new CancellationTokenSource(); Set("CancelToken", cancellation);
            var (connection, pid) = Connection(script, log); Task? disposing = null;
            try
            {
                var input = (Stream)connection.GetType().GetField("input", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(connection)!;
                input.Write(new byte[512 * 1024]); cancellation.Cancel();
                disposing = Task.Run(() => { try { connection.Dispose(); } catch (IOException) { } });
                Check(disposing.Wait(TimeSpan.FromSeconds(7)), "Cancellation left pending buffer blocked");
                Check(!Alive(pid), "Canceled server remained alive");
            }
            finally
            {
                StopTestProcess(pid); if (disposing != null) { try { disposing.Wait(TimeSpan.FromSeconds(3)); } catch { } }
                try { connection.Dispose(); } catch { } Set("CancelToken", new CancellationTokenSource());
                foreach (string file in Directory.GetFiles(directory)) File.Delete(file); Directory.Delete(directory);
            }
        });
        Test("failed_partial_export_does_not_block_dispose", () =>
        {
            string directory = Path.Combine(Path.GetTempPath(), "gral-buffer-failure-" + Guid.NewGuid()); Directory.CreateDirectory(directory);
            string script = Path.Combine(directory, "stall.py"), log = Path.Combine(directory, "stderr.log"); File.WriteAllText(script, "import time\ntime.sleep(60)\n");
            var (connection, pid) = Connection(script, log); Task? disposing = null;
            try
            {
                Array ragged = Array.CreateInstance(typeof(double[,]), 3000);
                for (int i = 0; i < 2999; i++) ragged.SetValue(new double[1,36], i);
                ragged.SetValue(new double[1,1], 2999);
                var init = connection.GetType().GetMethod("Init", BindingFlags.Instance | BindingFlags.NonPublic)!;
                var sending = Task.Run(() => Reject(() => { try { init.Invoke(connection, new object?[] { Array.Empty<string>(), new Dictionary<string, object> { ["ragged"] = ragged } }); } catch (TargetInvocationException e) { throw e.InnerException!; } }, "Ragged"));
                if (!sending.Wait(TimeSpan.FromSeconds(7))) { StopTestProcess(pid); sending.Wait(TimeSpan.FromSeconds(3)); throw new Exception("Partial export blocked error propagation"); }
                disposing = Task.Run(() => { try { connection.Dispose(); } catch { } });
                Check(disposing.Wait(TimeSpan.FromSeconds(7)), "Partial export blocked shutdown");
            }
            finally
            {
                StopTestProcess(pid); if (disposing != null) disposing.Wait(TimeSpan.FromSeconds(3));
                try { connection.Dispose(); } catch { } foreach (string file in Directory.GetFiles(directory)) File.Delete(file); Directory.Delete(directory);
            }
        });
        Test("server_dispose_terminates_only_its_stalled_process_tree", () =>
        {
            string directory = Path.Combine(Path.GetTempPath(), "gral-server-contract-" + Guid.NewGuid()); Directory.CreateDirectory(directory);
            string script = Path.Combine(directory, "stall.py"), log = Path.Combine(directory, "stderr.log");
            string readyFile = Path.Combine(directory, "child.pid");
            File.WriteAllText(script, "import subprocess,sys,time,pathlib\np=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])\npathlib.Path(" + JsonSerializer.Serialize(readyFile) + ").write_text(str(p.pid))\nprint('started',file=sys.stderr,flush=True)\ntime.sleep(60)\n");
            var (connection, pid) = Connection(script, log); int child = 0;
            try
            {
                var ready = Stopwatch.StartNew();
                while (child == 0 && ready.ElapsedMilliseconds < 3000)
                {
                    if (File.Exists(readyFile)) int.TryParse(File.ReadAllText(readyFile).Trim(), out child); if (child == 0) Thread.Sleep(20);
                }
                Check(child > 0, "Dummy child PID not received");
                Reject(() => connection.Dispose(), "timed out");
                Check(!Alive(pid) && !Alive(child), "GPU child process tree survived Dispose timeout");
            }
            finally { StopTestProcess(pid); if (child > 0) StopTestProcess(child); try { connection.Dispose(); } catch { } foreach (string file in Directory.GetFiles(directory)) File.Delete(file); Directory.Delete(directory); }
        });
        Test("server_dispose_propagates_nonzero_exit", () =>
        {
            string directory = Path.Combine(Path.GetTempPath(), "gral-server-exit-contract-" + Guid.NewGuid()); Directory.CreateDirectory(directory);
            string script = Path.Combine(directory, "exit.py"), log = Path.Combine(directory, "stderr.log"); File.WriteAllText(script, "import sys\nsys.exit(7)\n");
            var (connection, pid) = Connection(script, log);
            try { Reject(() => connection.Dispose(), "exit code 7"); Check(!Alive(pid), "Exited server remained alive"); }
            finally { StopTestProcess(pid); foreach (string file in Directory.GetFiles(directory)) File.Delete(file); Directory.Delete(directory); }
        });
        Test("cancellation_unblocks_server_read_and_terminates_owned_child", () =>
        {
            string directory = Path.Combine(Path.GetTempPath(), "gral-server-cancel-contract-" + Guid.NewGuid()); Directory.CreateDirectory(directory);
            string script = Path.Combine(directory, "block.py"), log = Path.Combine(directory, "stderr.log"); File.WriteAllText(script, "import time\ntime.sleep(60)\n");
            using var cancellation = new CancellationTokenSource(); Set("CancelToken", cancellation);
            var (connection, pid) = Connection(script, log);
            var read = Task.Run(() =>
            {
                try { return connection.GetType().GetMethod("ReadHeader", BindingFlags.Instance | BindingFlags.NonPublic)!.Invoke(connection, null); }
                catch (TargetInvocationException error) { throw error.InnerException!; }
            });
            try
            {
                cancellation.CancelAfter(100);
                Reject(() => read.WaitAsync(TimeSpan.FromSeconds(3)).GetAwaiter().GetResult(), "canceled");
                Check(!Alive(pid), "Canceled owned server remained alive");
            }
            finally
            {
                StopTestProcess(pid); try { connection.Dispose(); } catch { }
                Set("CancelToken", new CancellationTokenSource()); foreach (string file in Directory.GetFiles(directory)) File.Delete(file); Directory.Delete(directory);
            }
        });
        if (Model.GetType("GRAL_2001.CpuTrace") != null)
        Test("cpu_trace_binary_seed_identity_mapping_and_split_counter", () =>
        {
            ResidualSetup(); Set("IWET", 2); Set("NTEILMAX", 2);
            string directory = Path.Combine(Path.GetTempPath(), "gral-cpu-trace-contract-" + Guid.NewGuid());
            Directory.CreateDirectory(directory);
            var settings = new Dictionary<string, string> { ["INU_GPU_TRACE_SITUATION"] = "2", ["INU_GPU_RESIDUAL_TRACE_COUNT"] = "2", ["INU_GPU_CPU_TRACE"] = Path.Combine(directory, "fresh.bin"), ["INU_GPU_CPU_SEED_TRACE"] = Path.Combine(directory, "seeds.bin"), ["INU_GPU_CPU_RESIDUAL_TRACE"] = Path.Combine(directory, "residual.bin"), ["INU_GPU_CPU_TRACE_METRICS"] = Path.Combine(directory, "metrics.jsonl") };
            foreach (var setting in settings) Environment.SetEnvironmentVariable(setting.Key, setting.Value);
            try
            {
                Call("CpuTrace", "Prepare", 2); Call("CpuTrace", "InitialFresh", 1, 42u, 43u);
                Call("CpuTrace", "Fresh", 1, 1d, 2d, 3f, 4f, 10_000_001, 6u, 7u, 8d);
                Call("CpuTrace", "AddResidualCount", 2);
                Call("CpuTrace", "Residual", 1, 1, 2, 0, 1, 102u, 103u, 10d, 11d, 12f, 13f, 14, 15u, 16u, 17d);
                Call("CpuTrace", "Residual", 1, 1, 2, 0, 0, 100u, 101u, 20d, 21d, 22f, 23f, 24, 25u, 26u, 27d);
                Call("CpuTrace", "Save");
                double[] Read(string key) { byte[] bytes = File.ReadAllBytes(settings[key]); return Enumerable.Range(0, bytes.Length / 8).Select(i => BitConverter.ToDouble(bytes, i * 8)).ToArray(); }
                var seeds = Read("INU_GPU_CPU_SEED_TRACE"); Check(seeds.Length == 6 && seeds[2] == 42 && seeds[3] == 43, "Initial fresh seed binary differs");
                var fresh = Read("INU_GPU_CPU_TRACE"); Check(fresh.Length == 24 && fresh[8] == 1 && fresh[12] == 10_000_001 && fresh[15] == 8, "Final fresh binary differs");
                var residual = Read("INU_GPU_CPU_RESIDUAL_TRACE"); Check(residual.Length == 32 && residual[4] == 0 && residual[5] == 100 && residual[7] == 20 && residual[15] == 1 && residual[20] == 1 && residual[21] == 102, "Residual trace followed execution order rather than batch identity");
                using var metrics = JsonDocument.Parse(File.ReadAllText(settings["INU_GPU_CPU_TRACE_METRICS"]));
                Check(metrics.RootElement.GetProperty("residual_particles").GetInt64() == 2 && metrics.RootElement.GetProperty("residual_finished").GetInt64() == 2 && metrics.RootElement.GetProperty("fresh_above_10m_steps").GetInt64() == 1, "Split or long-trajectory counters differ");
            }
            finally { foreach (string key in settings.Keys) Environment.SetEnvironmentVariable(key, null); foreach (string file in Directory.GetFiles(directory)) File.Delete(file); Directory.Delete(directory); }
        });
        ExtendedContracts();
        int failed = Results.Count(x => JsonSerializer.Serialize(x).Contains("\"fail\""));
        if (args.Length > 0) File.WriteAllText(args[0], JsonSerializer.Serialize(new { status = failed == 0 ? "pass" : "fail", passed = Results.Count - failed, failed, tests = Results }, new JsonSerializerOptions { WriteIndented = true }));
        return failed == 0 ? 0 : 1;
    }
}
