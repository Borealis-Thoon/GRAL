using System.Reflection;
using System.Text.Json;

internal static partial class HostContracts
{
    private static byte[] ReferenceBytes(Array values)
    {
        using var stream = new MemoryStream(); using var writer = new BinaryWriter(stream);
        foreach (object value in values)
        {
            switch (value)
            {
                case byte v: writer.Write(v); break; case bool v: writer.Write(v ? (byte)1 : (byte)0); break;
                case short v: writer.Write(v); break; case ushort v: writer.Write(v); break;
                case int v: writer.Write(v); break; case uint v: writer.Write(v); break;
                case long v: writer.Write(v); break; case ulong v: writer.Write(v); break;
                case float v: writer.Write(v); break; case double v: writer.Write(v); break;
                default: throw new Exception("Missing reference type");
            }
        }
        return stream.ToArray();
    }
    private static byte[] ExportPayload(Array values)
    {
        using var stream = Export(Array.Empty<string>(), new Dictionary<string, object> { ["test"] = values });
        using var header = Header(stream);
        Check(header.RootElement.GetProperty("payload_bytes").GetInt64() == stream.Length - stream.Position, "Payload size differs");
        Check(header.RootElement.GetProperty("arrays")[0].GetProperty("dtype").GetString() == values.GetType().GetElementType()!.Name, "Dtype differs");
        using var payload = new MemoryStream(); stream.CopyTo(payload); return payload.ToArray();
    }
    private sealed class PartialReadStream : MemoryStream
    {
        internal PartialReadStream(byte[] bytes) : base(bytes) { }
        public override int Read(Span<byte> bytes) => base.Read(bytes[..Math.Min(bytes.Length, 3)]);
        public override int Read(byte[] bytes, int offset, int count) => base.Read(bytes, offset, Math.Min(count, 3));
    }
    private sealed class CountingReadStream : MemoryStream
    {
        internal int Reads;
        internal CountingReadStream(byte[] bytes) : base(bytes) { }
        public override int Read(Span<byte> bytes) { Reads++; return base.Read(bytes); }
        public override int Read(byte[] bytes, int offset, int count) { Reads++; return base.Read(bytes, offset, count); }
    }
    private static void ReadLeaf(Stream source, object target, string dtype, params int[] dims)
    {
        using var reader = new BinaryReader(source, System.Text.Encoding.UTF8, true);
        // Int64 has no public Program result field; exercise the shared wire reader directly.
        Call("GpuFieldImport", "ReadNested", reader, target, dims.ToList(), 0, dtype,
            dtype == "Double" || dtype == "Int64" ? 8 : 4, null!);
    }
    private static string[] CachedFields(object plan)
        => ((IEnumerable<string>)plan.GetType().GetProperty("Fields", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(plan)!).ToArray();
    private static object CachePrepare(object cache, string[] fields)
        => cache.GetType().GetMethod("Prepare", BindingFlags.Instance | BindingFlags.NonPublic)!.Invoke(cache, new object[] { fields })!;
    private static object NewCache()
    {
        try { return Activator.CreateInstance(Model.GetType("GRAL_2001.GpuInputCache", true)!, true)!; }
        catch (TargetInvocationException e) { throw e.InnerException!; }
    }
    private static void CacheCommit(object plan, string json = "{\"payload_bytes\":0}")
    {
        using var ack = JsonDocument.Parse(json);
        try { plan.GetType().GetMethod("Commit", BindingFlags.Instance | BindingFlags.NonPublic)!.Invoke(plan, new object[] { ack.RootElement }); }
        catch (TargetInvocationException e) { throw e.InnerException!; }
    }
    private static void ExtendedContracts()
    {
        var values = new Array[]
        {
            new byte[] { 0, 1, 255 }, new bool[] { false, true, false },
            new short[] { short.MinValue, 0, short.MaxValue }, new ushort[] { 0, 1, ushort.MaxValue },
            new int[] { int.MinValue, 0, int.MaxValue }, new uint[] { 0, 1, uint.MaxValue },
            new long[] { long.MinValue, 0, long.MaxValue }, new ulong[] { 0, 1, ulong.MaxValue },
            new float[] { BitConverter.Int32BitsToSingle(unchecked((int)0xFFC12345)), -0f, 0f, float.PositiveInfinity, 1.0000001f },
            new double[] { BitConverter.Int64BitsToDouble(unchecked((long)0xFFF8123456789ABC)), -0d, 0d, double.NegativeInfinity, 1.0000000000000002d }
        };
        foreach (Array source in values)
        {
            Test("export_span_" + source.GetType().GetElementType()!.Name + "_preserves_wire_bits", () =>
                Check(ExportPayload(source).SequenceEqual(ReferenceBytes(source)), "Primitive wire bits differ"));
        }
        foreach (Array source in values.Where(a => new[] { typeof(float), typeof(double), typeof(int), typeof(long) }.Contains(a.GetType().GetElementType())))
        {
            Test("import_span_" + source.GetType().GetElementType()!.Name + "_handles_partial_reads_and_exact_bits", () =>
            {
                Array target = Array.CreateInstance(source.GetType().GetElementType()!, source.Length);
                using var stream = new PartialReadStream(ReferenceBytes(source));
                ReadLeaf(stream, target, source.GetType().GetElementType()!.Name, source.Length);
                Check(ReferenceBytes(target).SequenceEqual(ReferenceBytes(source)), "Imported bits differ");
                Check(stream.Position == stream.Length, "Partial reads lost payload bytes");
            });
        }
        Test("export_rectangular_and_non_sz_arrays_use_exact_fallback_bytes", () =>
        {
            Array rectangular = new double[,] { { -0d, double.NaN }, { double.PositiveInfinity, 1.25d } };
            Array nonSz = Array.CreateInstance(typeof(int), new[] { 3 }, new[] { 5 });
            for (int i = 5; i < 8; i++) nonSz.SetValue(i == 5 ? int.MinValue : i, i);
            Check(!nonSz.GetType().IsSZArray, "Fixture is not a non-SZ array");
            foreach (Array source in new[] { rectangular, nonSz })
                Check(ExportPayload(source).SequenceEqual(ReferenceBytes(source)), "Fallback payload differs");
        });
        Test("export_empty_and_typed_null_emit_zero_payload", () =>
        {
            Check(ExportPayload(Array.Empty<int>()).Length == 0, "Empty array wrote payload");
            object old = Get("Xcoord");
            try
            {
                Set("Xcoord", null!); using var stream = Export(new[] { "Xcoord" }); using var header = Header(stream);
                var array = header.RootElement.GetProperty("arrays")[0];
                Check(array.GetProperty("is_null").GetBoolean() && array.GetProperty("bytes").GetInt64() == 0 && stream.Position == stream.Length, "Typed null frame differs");
            }
            finally { Set("Xcoord", old); }
        });
        Test("export_ragged_null_rows_preserve_nan_and_signed_zero_bits", () =>
        {
            double nan = BitConverter.Int64BitsToDouble(unchecked((long)0x7FF8123456789ABC));
            using var stream = Export(Array.Empty<string>(), new Dictionary<string, object> { ["ragged"] = new double[][] { new[] { nan, -0d }, null!, new[] { 1d } } });
            using var header = Header(stream); byte[] payload = new byte[48]; stream.ReadExactly(payload);
            Check(payload.SequenceEqual(ReferenceBytes(new[] { nan, -0d, 0d, 0d, 1d, 0d })), "Ragged padding changed payload bits");
        });
        Test("span_payloads_cross_one_mib_boundary_without_byte_loss", () =>
        {
            foreach (int length in new[] { 131071, 131072, 131073 })
            {
                double[] source = Enumerable.Range(0, length).Select(i => BitConverter.Int64BitsToDouble(i % 2 == 0 ? long.MinValue : i)).ToArray();
                byte[] expected = ReferenceBytes(source); Check(ExportPayload(source).SequenceEqual(expected), "Export chunk boundary differs at " + length);
                double[] target = new double[length]; using var stream = new PartialReadStream(expected);
                ReadLeaf(stream, target, "Double", length);
                Check(ReferenceBytes(target).SequenceEqual(expected), "Import chunk boundary differs at " + length);
            }
        });
        Test("import_rectangular_and_non_sz_fallbacks_handle_partial_reads", () =>
        {
            foreach (Array target in new Array[] { new int[2,2], Array.CreateInstance(typeof(int), new[] { 4 }, new[] { 5 }) })
            {
                byte[] expected = ReferenceBytes(new[] { int.MinValue, 0, 17, int.MaxValue }); using var stream = new PartialReadStream(expected);
                ReadLeaf(stream, target, "Int32", target.Rank == 2 ? new[] { 2, 2 } : new[] { 4 });
                Check(ReferenceBytes(target).SequenceEqual(expected), "Import fallback bits differ");
            }
        });
        Test("rectangular_fallback_crosses_one_mib_boundary_without_byte_loss", () =>
        {
            var source = new double[1, 131073];
            for (int i = 0; i < source.Length; i++) source[0,i] = i % 2 == 0 ? -0d : i + 0.125d;
            byte[] expected = ReferenceBytes(source);
            Check(ExportPayload(source).SequenceEqual(expected), "Rectangular export chunk boundary differs");
            var target = new double[1, 131073]; using var stream = new PartialReadStream(expected);
            ReadLeaf(stream, target, "Double", 1, 131073);
            Check(ReferenceBytes(target).SequenceEqual(expected), "Rectangular import chunk boundary differs");
        });
        Test("import_truncated_span_or_fallback_aborts_with_end_of_stream", () =>
        {
            foreach (Array target in new Array[] { new double[2], new double[1,2] })
            {
                using var stream = new PartialReadStream(new byte[15]);
                try { ReadLeaf(stream, target, "Double", target.Rank == 1 ? new[] { 2 } : new[] { 1, 2 }); }
                catch (EndOfStreamException) { continue; }
                throw new Exception("Truncated payload was accepted");
            }
        });
        Test("import_ragged_padding_rejects_nonzero_unallocated_cells", () =>
        {
            foreach (double[] payload in new[] { new[] { 1d, 0d, 0d, 0d }, new[] { 1d, 2d, 0d, 0d }, new[] { 1d, 0d, 3d, 0d } })
            {
                var target = new double[][] { new double[1], null! }; using var stream = new PartialReadStream(ReferenceBytes(payload));
                if (payload[1] == 0 && payload[2] == 0) { ReadLeaf(stream, target, "Double", 2, 2); Check(target[0][0] == 1, "Jagged value lost"); }
                else Reject(() => ReadLeaf(stream, target, "Double", 2, 2), payload[1] != 0 ? "padding" : "unallocated");
            }
        });
        Test("import_zero_padding_batches_reads_and_checks_numeric_zero", () =>
        {
            foreach (string dtype in new[] { "Single", "Double", "Int32", "Int64" })
            {
                int size = dtype == "Double" || dtype == "Int64" ? 8 : 4;
                var bytes = new byte[4096 * size];
                if (dtype == "Single" || dtype == "Double") bytes[size - 1] = 0x80;
                using var stream = new CountingReadStream(bytes);
                ReadLeaf(stream, null!, dtype, 4096);
                Check(stream.Position == bytes.Length && stream.Reads < 32, "Zero padding was not read in batches");
                bytes[bytes.Length - 1] = 0x7f;
                using var invalid = new PartialReadStream(bytes);
                Reject(() => ReadLeaf(invalid, null!, dtype, 4096), "unallocated");
                if (dtype == "Single" || dtype == "Double")
                {
                    var nan = dtype == "Single" ? ReferenceBytes(new[] { float.NaN }) : ReferenceBytes(new[] { double.NaN });
                    using var nanStream = new PartialReadStream(nan);
                    Reject(() => ReadLeaf(nanStream, null!, dtype, 1), "unallocated");
                }
                using var truncated = new PartialReadStream(bytes[..^1]);
                try { ReadLeaf(truncated, null!, dtype, 4096); throw new Exception("Truncated padding accepted"); }
                catch (EndOfStreamException) { }
            }
        });
        Test("import_zero_padding_crosses_chunk_boundary_and_rejects_truncated_or_nonzero_tail", () =>
        {
            foreach (string dtype in new[] { "Single", "Double", "Int32", "Int64" })
            {
                int size = dtype == "Double" || dtype == "Int64" ? 8 : 4;
                int count = 1024 * 1024 / size + 1;
                var bytes = new byte[count * size];
                if (dtype == "Single" || dtype == "Double")
                {
                    bytes[size - 1] = 0x80;
                    bytes[bytes.Length - 1] = 0x80;
                }
                using var valid = new CountingReadStream(bytes);
                ReadLeaf(valid, null!, dtype, count);
                Check(valid.Position == bytes.Length && valid.Reads < 32, "Padding chunk boundary differs: " + dtype);
                bytes[bytes.Length - size] = 1;
                using var invalid = new MemoryStream(bytes);
                Reject(() => ReadLeaf(invalid, null!, dtype, count), "unallocated");
                bytes[bytes.Length - size] = 0;
                using var truncated = new MemoryStream(bytes[..^1]);
                try { ReadLeaf(truncated, null!, dtype, count); throw new Exception("Truncated padding tail accepted: " + dtype); }
                catch (EndOfStreamException) { }
            }
        });
        Test("import_integer_padding_rejects_sign_bit_only_values", () =>
        {
            foreach (var sample in new[]
            {
                (Dtype: "Int32", Bytes: ReferenceBytes(new[] { int.MinValue })),
                (Dtype: "Int64", Bytes: ReferenceBytes(new[] { long.MinValue }))
            })
            {
                using var stream = new PartialReadStream(sample.Bytes);
                Reject(() => ReadLeaf(stream, null!, sample.Dtype, 1), "unallocated");
            }
        });
        Test("init_cache_new_grid_fields_invalidate_only_after_ack", () =>
        {
            string[] names = { "DDX", "DDY", "HorSlices" }; var old = names.ToDictionary(n => n, Get);
            try
            {
                foreach (string name in names) Set(name, new[] { -0f, 2f });
                object cache = NewCache(); object first = CachePrepare(cache, names);
                Check(CachedFields(first).SequenceEqual(names), "First grid fields omitted");
                Check(CachedFields(CachePrepare(cache, names)).SequenceEqual(names), "Prepare committed without ack");
                CacheCommit(first); Check(CachedFields(CachePrepare(cache, names)).Length == 0, "Equal grid fields not omitted");
                foreach (string name in names)
                {
                    ((float[])Get(name))[0] = 0f;
                    Check(CachedFields(CachePrepare(cache, names)).SequenceEqual(new[] { name }), "Signed zero bit change not detected: " + name);
                    object plan = CachePrepare(cache, names); Reject(() => CacheCommit(plan, "{\"payload_bytes\":1}"), "payload");
                    Check(CachedFields(CachePrepare(cache, names)).SequenceEqual(new[] { name }), "Failed ack advanced grid cache");
                    CacheCommit(plan);
                }
            }
            finally { foreach (string name in names) Set(name, old[name]); }
        });
        Test("init_cache_coordinates_require_explicit_opt_in_and_detect_mutation", () =>
        {
            string? setting = Environment.GetEnvironmentVariable("INU_GPU_CACHE_COORDINATES");
            string[] names = { "Xcoord", "YCoord", "ZCoord" }; var old = names.ToDictionary(n => n, Get);
            try
            {
                Set("Xcoord", new[] { 1d }); Set("YCoord", new[] { 2d }); Set("ZCoord", new[] { 3f });
                foreach (string? mode in new string?[] { null, "0", "1" })
                {
                    Environment.SetEnvironmentVariable("INU_GPU_CACHE_COORDINATES", mode); object cache = NewCache(); CacheCommit(CachePrepare(cache, names));
                    Check(CachedFields(CachePrepare(cache, names)).Length == (mode == "1" ? 0 : 3), "Coordinate opt-in differs");
                    ((double[])Get("Xcoord"))[0] += 1;
                    Check(CachedFields(CachePrepare(cache, names)).Contains("Xcoord"), "Changed coordinate omitted");
                }
            }
            finally { Environment.SetEnvironmentVariable("INU_GPU_CACHE_COORDINATES", setting); foreach (string name in names) Set(name, old[name]); }
        });
        Test("init_cache_rejects_invalid_coordinate_environment", () =>
        {
            string? setting = Environment.GetEnvironmentVariable("INU_GPU_CACHE_COORDINATES");
            try
            {
                foreach (string value in new[] { "", "true", "2", " 1", "1 " })
                { Environment.SetEnvironmentVariable("INU_GPU_CACHE_COORDINATES", value); Reject(() => NewCache(), "INU_GPU_CACHE_COORDINATES"); }
            }
            finally { Environment.SetEnvironmentVariable("INU_GPU_CACHE_COORDINATES", setting); }
        });
    }
}
