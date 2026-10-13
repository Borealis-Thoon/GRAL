using System.Collections;
using System.Collections.Concurrent;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;

internal static class EdgeChecks
{
    private static Type P = null!;
    private static Type W = null!;
    private static readonly BindingFlags Fields = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static;
    private static readonly List<object> Records = new();
    private static bool IsDictionary => P.GetField("Concentration2D", Fields) != null;
    private static FieldInfo? Field(string name) => P.GetField(name, Fields);
    private static object Get(string name) => Field(name)!.GetValue(null)!;
    private static void Set(string name, object value)
    {
        var f = Field(name);
        if (f == null) return;
        f.SetValue(null, f.FieldType.IsAssignableFrom(value.GetType()) ? value : Convert.ChangeType(value, f.FieldType));
    }
    private static Array MakeArray(Type arrayType, int[] dims, int d = 0)
    {
        var elementType = arrayType.GetElementType()!;
        var result = Array.CreateInstance(elementType, dims[d]);
        if (elementType.IsArray)
            for (int i = 0; i < dims[d]; i++) result.SetValue(MakeArray(elementType, dims, d + 1), i);
        return result;
    }
    private static void Allocate(string name, params int[] dims)
    {
        var f = Field(name);
        if (f != null) f.SetValue(null, MakeArray(f.FieldType, dims));
    }
    private static void Put(string name, double value, params int[] coordinates)
    {
        var f = Field(name);
        if (f == null) return;
        var a = (Array)f.GetValue(null)!;
        for (int d = 0; d < coordinates.Length - 1; d++) a = (Array)a.GetValue(coordinates[d])!;
        a.SetValue(Convert.ChangeType(value, a.GetType().GetElementType()!), coordinates[^1]);
    }
    private static void Init(int groups = 1, int nxl = 2, int nyl = 3, int slices = 2)
    {
        Set("NXL", nxl); Set("NYL", nyl); Set("NS", slices); Set("IOUTPUT", 0);
        Set("GralDx", 10F); Set("GralDy", 20F); Set("IKOOAGRAL", 1000); Set("JKOOAGRAL", 2000);
        Set("SourceGroups", Enumerable.Range(1, groups).ToList());
        Set("Odour", false); Set("ResultFileZipped", false); Set("WriteASCiiResults", false);
        Set("DepositionExist", false); Set("WetDeposition", false);
        foreach (string name in new[] { "Conz3d", "Conz3dDouble", "Conz3dp", "Conz3dm" }) Allocate(name, nxl + 2, nyl + 2, slices, groups);
        Allocate("TempConcArray", nxl + 2, nyl + 2);
        Allocate("Depo_conz", nxl + 2, nyl + 2, groups);
        Allocate("Q_cv0", slices, groups); Allocate("DisConcVar", slices, groups);
        foreach (string name in new[] { "Concentration2D", "Concentration2D_P", "Concentration2D_M" })
            if (Field(name) != null) ((ConcurrentDictionary<(int,int,int,int),double>)Get(name)).Clear();
    }
    private static void Concentration(string component, int i, int j, int slice, int group, double value)
    {
        string array = component switch { "main" => "Conz3d", "plus" => "Conz3dp", _ => "Conz3dm" };
        string dictionary = component switch { "main" => "Concentration2D", "plus" => "Concentration2D_P", _ => "Concentration2D_M" };
        Put(array, value, i, j, slice, group);
        if (component == "main") Put("Conz3dDouble", value, i, j, slice, group);
        if (IsDictionary) ((ConcurrentDictionary<(int,int,int,int),double>)Get(dictionary))[(i,j,slice,group)] = value;
    }
    private static double ReadMain(int i, int j, int slice, int group)
    {
        if (IsDictionary) return ((ConcurrentDictionary<(int,int,int,int),double>)Get("Concentration2D")).GetValueOrDefault((i,j,slice,group));
        var name = Field("Conz3dDouble") != null ? "Conz3dDouble" : "Conz3d";
        Array a = (Array)Get(name);
        foreach (int ix in new[] {i,j,slice}) a = (Array)a.GetValue(ix)!;
        return Convert.ToDouble(a.GetValue(group));
    }
    private static byte[] Write(string method, int group, int slice, int header)
    {
        Set("ResultFileHeader", header);
        using var ms = new MemoryStream();
        using (var writer = new BinaryWriter(ms, System.Text.Encoding.UTF8, true))
        {
            var result = W.GetMethod(method, Fields)!.Invoke(null, new object[] {writer, group, slice});
            if (!Equals(result, true)) throw new Exception(method + " returned false");
        }
        return ms.ToArray();
    }
    private static void Record(string category, string name, string method, int header, int group, int slice, byte[] bytes)
        => Records.Add(new { category, name, method, header, group, slice, length = bytes.Length, sha256 = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(), hex = Convert.ToHexString(bytes).ToLowerInvariant() });
    public static int Main(string[] args)
    {
        var dll = Path.GetFullPath(args[0]);
        string output = Path.GetFullPath(args[1]);
        string scratch = Path.GetFullPath(args[2]);
        Directory.CreateDirectory(scratch); Directory.SetCurrentDirectory(scratch);
        var assembly = Assembly.LoadFrom(dll);
        P = assembly.GetType("GRAL_2001.Program", true)!;
        W = assembly.GetType("GRAL_2001.ProgramWriters", true)!;
        string[] odourMethods = {"WriteOdourData", "WriteOdourDataStrongCompressed", "WriteOdourDataAllCompressed"};
        for (int mask = 0; mask < 8; mask++)
        {
            Init();
            Concentration("main", 1, 2, 0, 0, (mask & 1) != 0 ? 2 : 0);
            Concentration("plus", 1, 2, 0, 0, (mask & 2) != 0 ? 3 : 0);
            Concentration("minus", 1, 2, 0, 0, (mask & 4) != 0 ? 5 : 0);
            Put("Q_cv0", 7, 0, 0); Put("DisConcVar", 11, 0, 0);
            for (int k = 0; k < odourMethods.Length; k++)
                Record("odour", "mask_" + mask, odourMethods[k], -k - 1, 0, 0, Write(odourMethods[k], 0, 0, -k - 1));
        }
        Init(301);
        int[] groupIndices = {0, 1, 255, 256, 300};
        int[] sourceIds = {99, 108, 255, 256, 300};
        var sources = Enumerable.Range(1000,301).ToList();
        for (int x = 0; x < groupIndices.Length; x++) sources[groupIndices[x]] = sourceIds[x];
        Set("SourceGroups", sources);
        for (int x = 0; x < groupIndices.Length; x++)
        {
            Concentration("main", 1, 1, 0, groupIndices[x], 100 + x + 0.125);
            Concentration("main", 2, 3, 1, groupIndices[x], 200 + x + 0.375);
        }
        string[] concentrationMethods = {"WriteConcentrationData", "WriteConcentrationDataStrongCompressed", "WriteConcentrationDataAllCompressed"};
        foreach (int group in groupIndices)
            for (int slice = 0; slice < 2; slice++)
                for (int k = 0; k < concentrationMethods.Length; k++)
                    Record("concentration", "index_" + group + "_id_" + sources[group], concentrationMethods[k], -k - 1, group, slice, Write(concentrationMethods[k], group, slice, -k - 1));
        for (int mode = -1; mode >= -3; mode--)
        {
            Init(5);
            Set("SourceGroups", sourceIds.ToList()); Set("ResultFileHeader", mode); Set("ResultFileZipped", true);
            for (int x = 0; x < sourceIds.Length; x++) for (int slice = 0; slice < 2; slice++) Concentration("main", 1, 2, slice, x, 10 + x + slice * 0.5);
            string zip = Path.Combine(scratch, "output_" + (-mode) + ".grz");
            if (File.Exists(zip)) throw new Exception("Run in a fresh scratch directory");
            W.GetMethod("Write2DConcentrations")!.Invoke(Activator.CreateInstance(W), new object[] {7, zip});
            using var archive = ZipFile.OpenRead(zip);
            foreach (var entry in archive.Entries.OrderBy(x => x.FullName))
            {
                using var ms = new MemoryStream(); using var stream = entry.Open(); stream.CopyTo(ms);
                Record("grz_entry", entry.FullName, "Write2DConcentrations", mode, -1, -1, ms.ToArray());
            }
        }
        var retention = new List<object>();
        foreach (bool fixedSeed in new[] {false, true})
        {
            Init(); Set("UseFixedRndSeedVal", fixedSeed); Set("NTEILMAX", 100);
            ((ParallelOptions)Get("pOptions")).MaxDegreeOfParallelism = 2;
            Concentration("main", 1, 1, 0, 0, 123.25);
            double before = ReadMain(1,1,0,0);
            P.GetMethod("ParallelParticleDriver", Fields)!.Invoke(null, new object[] {1, 1});
            retention.Add(new {fixed_seed = fixedSeed, new_particle_count = 0, before, after = ReadMain(1,1,0,0)});
        }
        var report = new {assembly_sha256 = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(dll))).ToLowerInvariant(), dictionary = IsDictionary, records = Records, retention};
        File.WriteAllText(output, JsonSerializer.Serialize(report, new JsonSerializerOptions {WriteIndented = true}));
        Console.WriteLine($"records {Records.Count} retention {retention.Count}");
        return 0;
    }
}
