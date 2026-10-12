using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.Loader;
using System.Security.Cryptography;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
class Review
{
    const BindingFlags F=BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic;
    static int checks;
    static Dictionary<string,int> groups=new();
    static void Check(bool ok,string group) { if(!ok)throw new Exception(group); Interlocked.Increment(ref checks); lock(groups)groups[group]=groups.GetValueOrDefault(group)+1; }
    static Type P(Assembly a)=>a.GetType("GRAL_2001.Program",true);
    static void Set(Type t,string name,object value) { var f=t.GetField(name,F); f.SetValue(null,f.FieldType.IsInstanceOfType(value)?value:Convert.ChangeType(value,f.FieldType)); }
    static T Get<T>(Type t,string name)=>(T)t.GetField(name,F).GetValue(null);
    static Assembly Load(string path)=>new AssemblyLoadContext(Guid.NewGuid().ToString(),false).LoadFromAssemblyPath(Path.GetFullPath(path));
    static float[][][][] Storage(Type p,float initial)
    {
        var grid=Enumerable.Range(0,3).Select(_=>Enumerable.Range(0,3).Select(_=>Enumerable.Range(0,5).Select(_=>new float[1]).ToArray()).ToArray()).ToArray();
        grid[1][1][1][0]=initial;
        Set(p,"DXK",20);Set(p,"DYK",20);Set(p,"GridVolume",1);Set(p,"TAUS",1);Set(p,"NKK_Transient",3);Set(p,"HoKartTrans",new float[]{0,10,20,30,40});Set(p,"DZK_Trans",new float[]{1,1,1,1,1});Set(p,"Conz5d",grid);return grid;
    }
    static void StorageCall(MethodInfo m,double mass,double x=1,int reflected=0)=>m.Invoke(null,new object[]{reflected,1f,0f,mass,1d,.1f,x,1d,0});
    static void Main(string[] args)
    {
        var state=Load(args[0]);var storage=Load(args[1]);var stack=Load(args[2]);var vertical=Load(args[3]);var baseline=Load(args[4]);
        var p=P(state);var helper=p.GetMethod("ParticleStateIsFinite",F).CreateDelegate<Func<double,double,float,double,float,bool>>();
        Set(p,"NonFiniteParticleCount",0L);
        Parallel.For(0,8192,new ParallelOptions{MaxDegreeOfParallelism=8},i=>Check(helper(i%2==0?double.MaxValue:double.NaN,0,-0f,double.Epsilon,-1f)==(i%2==0),"state_parallel_return"));
        Check(Get<long>(p,"NonFiniteParticleCount")==4096,"state_parallel_count");
        var sp=P(storage);var st=storage.GetType("GRAL_2001.TransientConcentration",true);
        foreach(string name in new[]{"Conz5dZeitschleife","Conz5dZeitschleifeTransient"})
        {
            var method=st.GetMethod(name,F);var grid=Storage(sp,0);Set(st,"NonFiniteResidualWriteCount",0L);
            Parallel.For(0,4096,new ParallelOptions{MaxDegreeOfParallelism=8},i=>StorageCall(method,1,i%2==0?1:double.NaN));
            Check(grid[1][1][1][0]==2048,"storage_parallel_valid_sum");Check(Get<long>(st,"NonFiniteResidualWriteCount")==2048,"storage_parallel_rejected_count");
            float mass=float.MaxValue*.75f;grid=Storage(sp,0);Set(st,"NonFiniteResidualWriteCount",0L);
            Parallel.For(0,64,new ParallelOptions{MaxDegreeOfParallelism=8},_=>StorageCall(method,mass));
            Check(grid[1][1][1][0]==mass,"storage_overflow_race_preserves_one");Check(Get<long>(st,"NonFiniteResidualWriteCount")==63,"storage_overflow_race_count");
            foreach(float polluted in new[]{float.NaN,float.PositiveInfinity,float.NegativeInfinity})
            { grid=Storage(sp,polluted);Set(st,"NonFiniteResidualWriteCount",0L);StorageCall(method,1);Check(BitConverter.SingleToInt32Bits(grid[1][1][1][0])==BitConverter.SingleToInt32Bits(polluted),"prepolluted_storage_unchanged");Check(Get<long>(st,"NonFiniteResidualWriteCount")==1,"prepolluted_storage_count"); }
            grid=Storage(sp,7);Set(st,"NonFiniteResidualWriteCount",0L);StorageCall(method,double.NaN,double.NaN,1);Check(grid[1][1][1][0]==7 && Get<long>(st,"NonFiniteResidualWriteCount")==0,"reflected_storage_noop");
        }
        var vp=P(vertical);var bp=P(baseline);var vw=vertical.GetType("GRAL_2001.Zeitschleife",true);var bw=baseline.GetType("GRAL_2001.Zeitschleife",true);var cache=vw.GetNestedType("WindSearch",BindingFlags.NonPublic);var cm=vw.GetMethod("BinarySearch",F,null,new[]{typeof(float),cache.MakeByRefType()},null);var bm=bw.GetMethod("BinarySearch",F,null,new[]{typeof(float)},null).CreateDelegate<Func<float,int>>();
        float[] levels=Enumerable.Range(0,42).Select(i=>(float)(i*i+1)).ToArray();Set(vp,"HOKART",levels);Set(bp,"HOKART",(float[])levels.Clone());Set(vp,"NKK",39);Set(bp,"NKK",39);
        var heights=levels.Take(40).SelectMany(v=>new[]{MathF.BitDecrement(v),v,MathF.BitIncrement(v)}).Concat(new[]{float.NaN,float.PositiveInfinity,float.NegativeInfinity,0f,-0f,float.Epsilon}).ToArray();
        Parallel.For(0,8,new ParallelOptions{MaxDegreeOfParallelism=8},thread=>
        { object cs=Activator.CreateInstance(cache);foreach(float h in heights.Skip(thread).Concat(heights.Take(thread)))foreach(int repeat in new[]{0,1,2}) { object[] query={h,cs};int got=(int)cm.Invoke(null,query);cs=query[1];Check(got==bm(h),"independent_cache_parallel_sequences"); } });
        object def=System.Runtime.CompilerServices.RuntimeHelpers.GetUninitializedObject(cache);foreach(float h in heights){object[] q={h,def};Check((int)cm.Invoke(null,q)==bm(h),"default_cache_search");def=q[1];}
        object cached=Activator.CreateInstance(cache);object[] first={55f,cached};cm.Invoke(null,first);cached=first[1];
        levels=Enumerable.Range(0,42).Select(i=>(float)(i*100)).ToArray();Set(vp,"HOKART",levels);Set(bp,"HOKART",(float[])levels.Clone());object[] replacement={55f,cached};Check((int)cm.Invoke(null,replacement)==bm(55f),"same_height_grid_replacement");cached=replacement[1];
        Set(vp,"NKK",1);Set(bp,"NKK",1);object[] countChange={4000f,cached};Check((int)cm.Invoke(null,countChange)==bm(4000f),"count_change_cache_reset");
        var sk=P(stack);var sw=stack.GetType("GRAL_2001.Zeitschleife",true);var driver=sw.GetMethod("Calculate",F);
        Set(sk,"UseFixedRndSeedVal",true);Set(sk,"Xcoord",new double[]{0,0});Set(sk,"YCoord",new double[]{0,0});Set(sk,"ZCoord",new float[]{0,1});Set(sk,"ParticleMass",new double[]{0,1});Set(sk,"ParticleSG",new byte[]{0,1});Set(sk,"ParticleSource",new int[]{0,1});Set(sk,"ParticleMode",new byte[]{0,0});Set(sk,"ParticleVsed",new float[2]);Set(sk,"ParticleVdep",new float[2]);Set(sk,"SourceType",new byte[]{0,3});Set(sk,"SourceGroups",new List<int>{1});Set(sk,"DDX",new float[]{20,20});Set(sk,"DDY",new float[]{20,20});Set(sk,"ReceptorNumber",0);Set(sk,"ReceptorsAvailable",false);Set(sk,"LogLevel",0);Set(sk,"ISTATIONAER",1);Set(sk,"Topo",0);Set(sk,"EmissionTimeseriesExist",false);Set(sk,"DXK",20);Set(sk,"DYK",20);Set(sk,"GralDx",20);Set(sk,"GralDy",20);Set(sk,"GralDz",10);Set(sk,"GridVolume",4000);Set(sk,"TAUS",30);Set(sk,"EtaMinGral",0);Set(sk,"XsiMinGral",0);Set(sk,"EtaMaxGral",200);Set(sk,"XsiMaxGral",200);
        foreach(int ns in new[]{0,1,511,512,513,4096}){Set(sk,"NS",ns);driver.Invoke(null,new object[]{1});Check(true,"stack_actual_entry_boundary");}
        var result=new{status="pass",checks,groups,maximum_parallel_workers=8,scope="Additional actual-DLL component checks only; no Main fault injection, speed measurement, negative-dimension contract or full NS=512/513 tracking claim.",dlls=args.Take(5).Select(path=>new{path,sha256=Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(path)))})};
        File.WriteAllText(args[5],JsonSerializer.Serialize(result,new JsonSerializerOptions{WriteIndented=true}));Console.WriteLine(JsonSerializer.Serialize(new{result.status,checks}));
    }
}
