using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Linq.Expressions;
using System.Reflection;
using System.Runtime.Loader;
using System.Security.Cryptography;
using System.Text.Json;

sealed class Engine
{
    internal readonly Assembly Assembly;
    internal readonly Type ProgramType;
    internal readonly Type WindType;
    internal readonly Func<float,int> Search;
    internal readonly Func<int,int,float,double,double,float,(float,float,float,int)> Wind;
    internal readonly Action<int> Driver;
    internal readonly string Dll;
    internal Engine(string dll)
    {
        Dll=Path.GetFullPath(dll);
        Assembly=new AssemblyLoadContext(Guid.NewGuid().ToString(),true).LoadFromAssemblyPath(Dll);
        ProgramType=Assembly.GetType("GRAL_2001.Program",true)!;
        WindType=Assembly.GetType("GRAL_2001.Zeitschleife",true)!;
        const BindingFlags f=BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic;
        Search=(Func<float,int>)WindType.GetMethod("BinarySearch",f,null,new[]{typeof(float)},null)!.CreateDelegate(typeof(Func<float,int>));
        Wind=(Func<int,int,float,double,double,float,(float,float,float,int)>)WindType.GetMethod("IntWindCalculate",f,null,new[]{typeof(int),typeof(int),typeof(float),typeof(double),typeof(double),typeof(float)},null)!.CreateDelegate(typeof(Func<int,int,float,double,double,float,(float,float,float,int)>));
        Driver=(Action<int>)WindType.GetMethod("Calculate",f,null,new[]{typeof(int)},null)!.CreateDelegate(typeof(Action<int>));
    }
    internal void Set(string name, object value)
    {
        FieldInfo field=ProgramType.GetField(name,BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic)!;
        field.SetValue(null,field.FieldType.IsInstanceOfType(value)?value:Convert.ChangeType(value,field.FieldType));
    }
    internal int Constant(string name)=>(int)Assembly.GetType("GRAL_2001.Consts",true)!.GetField(name)!.GetValue(null)!;
    internal object Get(string name)=>ProgramType.GetField(name,BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic)!.GetValue(null)!;
    internal void Profile(float[] levels,int nkk)
    {
        Set("HOKART",levels);Set("NKK",nkk);
    }
    internal Func<int,Func<float,int>> CachedFactory()
    {
        Type cache=WindType.GetNestedType("WindSearch",BindingFlags.NonPublic)!;
        var hint=Expression.Parameter(typeof(int),"hint");var height=Expression.Parameter(typeof(float),"height");
        var state=Expression.Variable(cache,"state");
        var ctor=cache.GetConstructor(Type.EmptyTypes)!;
        var method=WindType.GetMethod("BinarySearch",BindingFlags.Static|BindingFlags.NonPublic,null,new[]{typeof(float),cache.MakeByRefType()},null)!;
        var init=Expression.Assign(state,Expression.New(ctor));
        var index=Expression.Field(state,"Index");var lastHeight=Expression.Field(state,"Height");
        var initialize=Expression.Block(init,Expression.Assign(index,hint),Expression.Assign(lastHeight,Expression.Constant(float.NaN)));
        var inner=Expression.Lambda<Func<float,int>>(Expression.Call(method,height,state),height);
        return Expression.Lambda<Func<int,Func<float,int>>>(Expression.Block(new[]{state},initialize,inner),hint).Compile();
    }
    internal Func<float,int,int> AllHints()
    {
        Type cache=WindType.GetNestedType("WindSearch",BindingFlags.NonPublic)!;
        var height=Expression.Parameter(typeof(float),"height");var hint=Expression.Parameter(typeof(int),"hint");var state=Expression.Variable(cache,"state");
        var method=WindType.GetMethod("BinarySearch",BindingFlags.Static|BindingFlags.NonPublic,null,new[]{typeof(float),cache.MakeByRefType()},null)!;
        var inner=Expression.Lambda<Func<float,int,int>>(Expression.Block(Expression.Assign(Expression.Field(state,"Index"),hint),Expression.Assign(Expression.Field(state,"Height"),Expression.Constant(float.NaN)),Expression.Call(method,height,state)),height,hint);
        return Expression.Lambda<Func<Func<float,int,int>>>(Expression.Block(new[]{state},Expression.Assign(state,Expression.New(cache.GetConstructor(Type.EmptyTypes)!)),inner)).Compile()();
    }
    internal Func<Func<int,int,float,double,double,float,(float,float,float,int)>> CachedWindFactory()
    {
        Type cache=WindType.GetNestedType("WindSearch",BindingFlags.NonPublic)!;
        var state=Expression.Variable(cache,"state");
        var args=new[]{Expression.Parameter(typeof(int),"i"),Expression.Parameter(typeof(int),"j"),Expression.Parameter(typeof(float),"a"),Expression.Parameter(typeof(double),"x"),Expression.Parameter(typeof(double),"y"),Expression.Parameter(typeof(float),"z")};
        var method=WindType.GetMethod("IntWindCalculate",BindingFlags.Static|BindingFlags.NonPublic,null,new[]{typeof(int),typeof(int),typeof(float),typeof(double),typeof(double),typeof(float),cache.MakeByRefType()},null)!;
        var inner=Expression.Lambda<Func<int,int,float,double,double,float,(float,float,float,int)>>(Expression.Call(method,args.Cast<Expression>().Append(state)),args);
        return Expression.Lambda<Func<Func<int,int,float,double,double,float,(float,float,float,int)>>>(Expression.Block(new[]{state},Expression.Assign(state,Expression.New(cache.GetConstructor(Type.EmptyTypes)!)),inner)).Compile();
    }
    internal void WindFields(float[] levels,int nkk)
    {
        Profile(levels,nkk);Set("DXK",20F);Set("DYK",20F);Set("AHMIN",0F);Set("IKOOAGRAL",0);Set("JKOOAGRAL",0);
        float[][][] Grid(int component)=>Enumerable.Range(0,4).Select(i=>Enumerable.Range(0,4).Select(j=>Enumerable.Range(0,nkk+3).Select(k=>(float)(component*0.25+i*0.125+j*0.0625+k*0.03125)).ToArray()).ToArray()).ToArray();
        Set("UK",Grid(1));Set("VK",Grid(2));Set("WK",Grid(3));Set("DZK",Enumerable.Repeat(10F,nkk+3).ToArray());
        Set("Topo",Constant("TerrainAvailable"));Set("BuildingsExist",false);
        Set("MetProfileNumb",1);Set("MeasurementHeight",new float[]{0,10});Set("ObsWindU",new float[]{0,2});Set("ObsWindV",new float[]{0,1});Set("Ob",Enumerable.Range(0,4).Select(_=>new float[]{-100,-100,-100,-100}).ToArray());
    }
    internal void EarlyDriver(int ns)
    {
        Set("NS",ns);Set("UseFixedRndSeedVal",true);Set("Xcoord",new double[]{0,0});Set("YCoord",new double[]{0,0});Set("ZCoord",new float[]{0,1});Set("ParticleMass",new double[]{0,1});Set("ParticleSG",new byte[]{0,1});Set("ParticleSource",new int[]{0,1});Set("ParticleMode",new byte[]{0,0});Set("ParticleVsed",new float[2]);Set("ParticleVdep",new float[2]);Set("SourceType",new byte[]{0,3});Set("SourceGroups",new List<int>{1});Set("DDX",new float[]{20,20});Set("DDY",new float[]{20,20});Set("ReceptorNumber",0);Set("ReceptorsAvailable",false);Set("LogLevel",0);Set("ISTATIONAER",1);Set("Topo",Constant("TerrainFlat"));Set("EmissionTimeseriesExist",false);Set("DXK",20F);Set("DYK",20F);Set("GralDx",20F);Set("GralDy",20F);Set("GralDz",10F);Set("GridVolume",4000F);Set("TAUS",30F);Set("EtaMinGral",0F);Set("XsiMinGral",0F);Set("EtaMaxGral",200F);Set("XsiMaxGral",200F);
    }
}

static class Fixture
{
    static long checks;
    static readonly List<object> Failures=new();
    static readonly Dictionary<string,long> Groups=new();
    static void Check(bool pass,string group,object context)
    {
        checks++;Groups[group]=Groups.GetValueOrDefault(group)+1;
        if(!pass && Failures.Count<30)Failures.Add(new{group,context});
    }
    static int[] Bits((float,float,float,int) value)=>new[]{BitConverter.SingleToInt32Bits(value.Item1),BitConverter.SingleToInt32Bits(value.Item2),BitConverter.SingleToInt32Bits(value.Item3),value.Item4};
    static (int[]? bits,string? error) Result(Func<(float,float,float,int)> f)
    {
        try{return(Bits(f()),null);}catch(Exception e){return(null,e.GetType().FullName);}
    }
    static bool Equal((int[]? bits,string? error) a,(int[]? bits,string? error) b)=>a.error==b.error && (a.bits==null?b.bits==null:b.bits!=null&&a.bits.SequenceEqual(b.bits));
    static IEnumerable<(string name,float[] levels)> Profiles(int n)
    {
        float[] Base()=>Enumerable.Range(0,n+3).Select(i=>i*10F).ToArray();
        yield return("strict",Base());
        var p=Base();p[0]=-0F;yield return("signed_zero_origin",p);
        p=Base();p[Math.Max(1,n/2)]=p[Math.Max(1,n/2)-1];yield return("duplicate",p);
        p=Base();p[Math.Max(1,n/2)]=-5F;yield return("nonmonotone",p);
        p=Base();p[Math.Max(1,n/2)]=float.NaN;yield return("NaN_profile",p);
        p=Base();p[Math.Max(1,n/2)]=float.PositiveInfinity;yield return("infinite_profile",p);
        p=Base();p[0]=float.NegativeInfinity;yield return("infinite_origin",p);
    }
    static float[] Heights(float[] p,int n)
    {
        var h=new List<float>{0,-0F,float.NaN,float.PositiveInfinity,float.NegativeInfinity,float.MaxValue,float.MinValue,float.Epsilon,-float.Epsilon};
        for(int k=0;k<=n;k++){h.Add(p[k]);h.Add(MathF.BitIncrement(p[k]));h.Add(MathF.BitDecrement(p[k]));}
        var rng=new Random(20261012+n);var bytes=new byte[4];
        for(int i=0;i<512;i++){rng.NextBytes(bytes);h.Add(BitConverter.ToSingle(bytes));}
        return h.ToArray();
    }
    static void Correctness(Engine before,Engine stack,Engine candidate,string output)
    {
        var watch=Stopwatch.StartNew();var factory=candidate.CachedFactory();var windFactory=candidate.CachedWindFactory();
        int profiles=0;long tupleErrors=0,tupleValues=0;
        foreach(int n in new[]{1,7,8,16,162})foreach(var (name,p) in Profiles(n))
        {
            profiles++;before.Profile((float[])p.Clone(),n);candidate.Profile((float[])p.Clone(),n);
            float[] hs=Heights(p,n);var all=candidate.AllHints();var sequence=factory(0);
            foreach(float height in hs)
            {
                int expected=before.Search(height);
                for(int hint=-1;hint<=n+1;hint++)Check(all(height,hint)==expected,"search_all_hints",new{n,name,height_bits=BitConverter.SingleToInt32Bits(height),hint,expected});
                Check(sequence(height)==expected,"search_sequence",new{n,name,height_bits=BitConverter.SingleToInt32Bits(height),expected});
                Check(sequence(height)==expected,"search_same_height",new{n,name,height_bits=BitConverter.SingleToInt32Bits(height),expected});
                Check(candidate.Search(height)==expected,"unchanged_public_search",new{n,name,height_bits=BitConverter.SingleToInt32Bits(height)});
            }
            before.WindFields((float[])p.Clone(),n);candidate.WindFields((float[])p.Clone(),n);var cachedWind=windFactory();
            foreach(int topo in new[]{before.Constant("TerrainAvailable"),before.Constant("TerrainFlat")})foreach(bool buildings in new[]{false,true})
            {
                before.Set("Topo",topo);candidate.Set("Topo",topo);before.Set("BuildingsExist",buildings);candidate.Set("BuildingsExist",buildings);
                foreach(float z in hs)
                {
                    var expected=Result(()=>before.Wind(1,1,0.5F,27.125,33.625,z));var actual=Result(()=>candidate.Wind(1,1,0.5F,27.125,33.625,z));var cached=Result(()=>cachedWind(1,1,0.5F,27.125,33.625,z));
                    Check(Equal(expected,actual),"public_wind_tuple",new{n,name,topo,buildings,z_bits=BitConverter.SingleToInt32Bits(z),expected,actual});
                    Check(Equal(expected,cached),"cached_wind_tuple",new{n,name,topo,buildings,z_bits=BitConverter.SingleToInt32Bits(z),expected,cached});
                    if(expected.error==null)tupleValues++;else tupleErrors++;
                }
            }
        }
        foreach(int n in new[]{1,7,8,16,162})
        {
            float[] p=Enumerable.Range(0,n+3).Select(i=>i*10F).ToArray();before.Profile((float[])p.Clone(),n);candidate.Profile((float[])p.Clone(),n);var search=factory(0);
            _=search(5F);float[] replacement=p.Select(v=>v*2).ToArray();before.Profile((float[])replacement.Clone(),n);candidate.Profile((float[])replacement.Clone(),n);
            foreach(float h in Heights(replacement,n))Check(search(h)==before.Search(h),"array_replacement_invalidation",new{n,height_bits=BitConverter.SingleToInt32Bits(h)});
            if(n>1){before.Set("NKK",n-1);candidate.Set("NKK",n-1);foreach(float h in Heights(replacement,n-1))Check(search(h)==before.Search(h),"count_change_invalidation",new{n,height_bits=BitConverter.SingleToInt32Bits(h)});}
            float[] mutable=(float[])candidate.Get("HOKART");for(int k=1;k<mutable.Length;k++)mutable[k]*=3F;before.Profile((float[])mutable.Clone(),(int)candidate.Get("NKK"));search=factory(0);
            foreach(float h in Heights(mutable,(int)candidate.Get("NKK")))Check(search(h)==before.Search(h),"in_place_mutation_new_particle_state",new{n,height_bits=BitConverter.SingleToInt32Bits(h)});
        }
        foreach(int ns in new[]{1,9,512,513})
        {
            before.EarlyDriver(ns);stack.EarlyDriver(ns);candidate.EarlyDriver(ns);
            try{before.Driver(1);stack.Driver(1);candidate.Driver(1);Check(true,"production_stack_declaration_entry",new{ns,path="initial-domain-removal after slice declaration",normal_tracking=false});}catch(Exception e){Check(false,"production_stack_declaration_entry",new{ns,error=e.ToString()});}
        }
        var result=new{status=Failures.Count==0?"pass":"fail",checks,groups=Groups,profiles,tuple_values=tupleValues,matched_tuple_exceptions=tupleErrors,elapsed_seconds=watch.Elapsed.TotalSeconds,dlls=new[]{before,stack,candidate}.Select(e=>new{path=e.Dll,sha256=Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(e.Dll)))}),failures=Failures,profile_contract="HOKART is immutable within a particle; replacement or NKK change invalidates automatically. In-place changes tested after explicit new-particle state preparation. No arbitrary in-place-change detection is claimed.",stack_scope="Actual Calculate entry reaches allocation then removes an out-of-domain particle; full tracking read-before-write is covered separately by Main runs and source audit. No allocation or timing benchmark was run in this correctness mode."};
        File.WriteAllText(output,JsonSerializer.Serialize(result,new JsonSerializerOptions{WriteIndented=true}));Console.WriteLine(JsonSerializer.Serialize(new{result.status,result.checks,result.profiles,result.elapsed_seconds,result.failures}));
        if(Failures.Count>0)Environment.ExitCode=1;
    }
    static void Main(string[] args)
    {
        if(args.Length!=5 || args[0]!="correctness")throw new ArgumentException("correctness baseline.dll stack.dll vertical.dll output.json");
        Correctness(new Engine(args[1]),new Engine(args[2]),new Engine(args[3]),args[4]);
    }
}
