using System.Text.Json;
class Program
{
    // Same array builder and allocation shape as ProgramFunctions.cs in PR #64.
    public static T[] CreateArray<T>(int cnt, Func<T> itemCreator)
    {
        T[] result = new T[cnt];
        for (int i = 0; i < result.Length; i++)
        {
            result[i] = itemCreator();
        }
        return result;
    }
    static double[][][][] Allocate(int nx,int ny,int ns,int sg) => CreateArray<double[][][]>(nx + 2, () => CreateArray<double[][]>(ny + 2, () => CreateArray<double[]>(ns, () => new double[sg])));
    static object Memory(string name,int nx,int ny,int ns,int sg)
    {
        long payload=8L*(nx+2)*(ny+2)*ns*sg;
        if(payload>500L*1024*1024)throw new Exception("Allocation cap");
        GC.Collect();GC.WaitForPendingFinalizers();GC.Collect();
        long before=GC.GetAllocatedBytesForCurrentThread();
        var grid=Allocate(nx,ny,ns,sg);
        long allocated=GC.GetAllocatedBytesForCurrentThread()-before;
        long cells=0; foreach(var x in grid)foreach(var y in x)foreach(var z in y)cells+=z.Length;
        if(cells!=(long)(nx+2)*(ny+2)*ns*sg || allocated<payload)throw new Exception("Shape or allocation");
        GC.KeepAlive(grid);
        return new {name,nx,ny,slices=ns,source_groups=sg,payload_bytes=payload,allocated_bytes=allocated,jagged_and_closure_overhead_bytes=allocated-payload};
    }
    // Exact operation at the production sites: conc = masse * idt, then locked add.
    static float FloatSum(double[] a) {float[] cell=new float[1];foreach(double masse in a){double idt=1;double conc=masse*idt;lock(cell){cell[0]+=(float)conc;}}return cell[0];}
    static float DoubleSum(double[] a) {double[] cell=new double[1];foreach(double masse in a){double idt=1;double conc=masse*idt;lock(cell){cell[0]+=conc;}}return (float)cell[0];}
    static object Precision(int n,string distribution)
    {
        long units=0;double[] a=new double[n];
        for(int i=0;i<n;i++){
            long u=distribution switch {"equal"=>1024L,"mixed_1e3"=>i%2==0 ? (1L<<24):(1L<<14),"mixed_1e7"=>i%4==0 ? (1L<<24):1L,_=>throw new Exception()};
            units+=u;a[i]=u/16777216.0;
        }
        if(units>9007199254740992L)throw new Exception("Reference exceeds exact binary64 integer");
        double exact=units/16777216.0;float expected=(float)exact;
        var fs=new List<float>();var ds=new List<float>();
        for(int r=0;r<8;r++){
            var b=(double[])a.Clone();var random=new Random(700+r);
            for(int i=b.Length-1;i>0;i--){int j=random.Next(i+1);(b[i],b[j])=(b[j],b[i]);}
            fs.Add(FloatSum(b));ds.Add(DoubleSum(b));
        }
        if(ds.Any(x=>x!=expected))throw new Exception("Double final output differs from exact reference");
        return new {contributions=n,distribution,permutations=8,exact_sum=exact,reference_float=expected,float_values=fs,double_values=ds,float_unique_outputs=fs.Distinct().Count(),double_unique_outputs=ds.Distinct().Count(),float_range=(double)fs.Max()-fs.Min(),double_range=(double)ds.Max()-ds.Min(),max_float_relative_error=fs.Max(x=>Math.Abs(x-exact))/exact,max_double_relative_error=ds.Max(x=>Math.Abs(x-exact))/exact};
    }
    static void Main(string[] args)
    {
        GC.KeepAlive(Allocate(1,1,1,1)); // JIT the allocation before counting bytes.
        var memory=new[]{Memory("synthetic_1sg",100,100,1,1),Memory("synthetic_108sg",100,100,9,108),Memory("reported_500m_shape",114,82,9,108),Memory("same_domain_250m_shape",228,164,9,108)};
        var precision=new List<object>();foreach(int n in new[]{3000,100000,1000000})foreach(string d in new[]{"equal","mixed_1e3","mixed_1e7"})precision.Add(Precision(n,d));
        File.WriteAllText(args[0],JsonSerializer.Serialize(new {status="pass",memory,precision,limits=new[]{"Allocation-only shape checks; these are not production-process peak measurements.","Permutation inputs are constructed positive dyadic contributions, not samples extracted from a production run.","Every double sum equals the correctly rounded binary32 reference for these cases; arbitrary parallel runs are not guaranteed bitwise reproducible."}},new JsonSerializerOptions{WriteIndented=true}));
        Console.WriteLine("PASS 4 allocation shapes 72 permutation cases");
    }
}
