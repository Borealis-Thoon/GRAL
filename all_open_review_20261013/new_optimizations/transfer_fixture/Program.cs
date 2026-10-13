using System.Reflection;
using System.Diagnostics;
using System.Text.Json;
class Test {
 static Type P; static BindingFlags F=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Static;
 static void Set(string n,object v) {var f=P.GetField(n,F);if(f==null)throw new Exception(n);f.SetValue(null,v is Array || f.FieldType.IsInstanceOfType(v)?v:Convert.ChangeType(v,f.FieldType));}
 static object Get(string n)=>P.GetField(n,F).GetValue(null);
 static string[] Names={"ParticleSource","ParticleSG","Xcoord","YCoord","ZCoord","ParticleMass","SourceType","ParticleVsed","ParticleVdep","ParticleMode"};
 static void Source(string kind,int count) {foreach(string k in new[]{"PS","LS","TS","AS"}){Set(k+"_Count",k==kind?1:0);Set(k+"_ER",new double[]{0,1});Set(k+"_PartNumb",new int[2]);}Set("NTEILMAX",count);Set("TAUS",30);Set("TPS",30);Set("GridVolume",8000);}
 static object Allocation(Assembly a,bool reuse) {
  var method=a.GetType("GRAL_2001.ParticleManagement").GetMethod("Calculate",F);var action=method.CreateDelegate<Func<int>>();Console.SetOut(TextWriter.Null);var rows=new List<object>();
  Array[] previous=null;int prior=-1;int calls=0;
  foreach(var (kind,requested) in new[]{("PS",100),("AS",100),("LS",3000),("TS",3000),("PS",100),("PS",100000),("AS",100000),("PS",1000000),("TS",1000000),("PS",100)}) {
   Source(kind,requested);long before=GC.GetTotalAllocatedBytes(true);var sw=Stopwatch.StartNew();int actual=action();sw.Stop();long bytes=GC.GetTotalAllocatedBytes(true)-before;var arrays=Names.Select(n=>(Array)Get(n)).ToArray();int retained=previous==null?0:arrays.Zip(previous).Count(x=>ReferenceEquals(x.First,x.Second));
   if(actual!=requested||arrays.Any(x=>x.Length!=actual+1)||retained!=(reuse&&actual==prior?10:0))throw new Exception("Array allocation/reuse invariant");
   rows.Add(new{kind,requested,actual,retained_arrays=retained,allocated_bytes=bytes,elapsed_ms=sw.Elapsed.TotalMilliseconds});previous=arrays;prior=actual;calls++;
  }
  return new{status="pass",scope="Actual ParticleManagement.Calculate via delegate; equal-size changed source type, growth and shrink; arrays initialized later by real Main tests",calls,rows};
 }
 static void A1(string name,double value) {var a=(Array)Get(name);a.SetValue(Convert.ChangeType(value,a.GetType().GetElementType()),1);}
 static object Initialize(Assembly a) {
  Console.SetOut(TextWriter.Null);var allocate=a.GetType("GRAL_2001.ParticleManagement").GetMethod("Calculate",F).CreateDelegate<Func<int>>();var init=a.GetType("GRAL_2001.StartCoordinates").GetMethod("Calculate",F).CreateDelegate<Action>();
  foreach(var field in P.GetFields(F).Where(x=>x.Name.StartsWith("PS_")&&x.FieldType.IsArray&&x.FieldType.GetArrayRank()==1))field.SetValue(null,Array.CreateInstance(field.FieldType.GetElementType(),2));
  Set("ISTATIONAER",1);Set("Topo",0);Set("BuildingsExist",false);Set("UseFixedRndSeedVal",true);Set("SourceGroups",new List<int>{1,3});Set("XsiMaxGral",200);Set("EtaMaxGral",200);((ParallelOptions)Get("pOptions")).MaxDegreeOfParallelism=4;
  long checkedValues=0;var rows=new List<object>();
  foreach(int mode in new[]{0,1,2,0}) {
   Source("PS",100);A1("PS_X",100);A1("PS_Y",100);A1("PS_effqu",2);A1("PS_Mode",mode);A1("PS_SG",mode==0?1:3);A1("PS_V_sed",0.1);A1("PS_V_Dep",0.2);A1("PS_ER_Dep",3);allocate();
   foreach(string name in Names){var ar=(Array)Get(name);var type=ar.GetType().GetElementType();object poison=type==typeof(double)?double.NaN:type==typeof(float)?float.NaN:type==typeof(byte)?(byte)255:-999;for(int i=1;i<ar.Length;i++)ar.SetValue(Convert.ChangeType(poison,type),i);}
   init();double mass=mode==2?3.0/100*1000000000/8000/30:1.0/100*(1000000000.0/8000/3600);
   var expected=new Dictionary<string,double>{{"ParticleSource",1},{"ParticleSG",mode==0?1:3},{"Xcoord",100},{"YCoord",100},{"ZCoord",2},{"ParticleMass",mass},{"SourceType",0},{"ParticleVsed",mode==0?0:(float)0.1},{"ParticleVdep",mode==0?0:(float)0.2},{"ParticleMode",mode}};
   foreach(var pair in expected){var ar=(Array)Get(pair.Key);for(int i=1;i<=100;i++){double value=Convert.ToDouble(ar.GetValue(i));if(value!=pair.Value)throw new Exception("Initializer stale value "+pair.Key+" "+value+" != "+pair.Value);checkedValues++;}}
   rows.Add(new{mode,source_group=mode==0?1:3,particles=100});
  }
  return new{status="pass",scope="Actual StartCoordinates.Calculate overwrites poisoned particle values for concentration, concentration+deposition, deposition-only, then concentration again",checked_values=checkedValues,rows};
 }
 static double[][][][] DG(int nx,int ny,int ns,int sg)=>Enumerable.Range(0,nx).Select(_=>Enumerable.Range(0,ny).Select(_=>Enumerable.Range(0,ns).Select(_=>new double[sg]).ToArray()).ToArray()).ToArray();
 static float[][][][] FG(int nx,int ny,int ns,int sg)=>Enumerable.Range(0,nx).Select(_=>Enumerable.Range(0,ny).Select(_=>Enumerable.Range(0,ns).Select(_=>new float[sg]).ToArray()).ToArray()).ToArray();
 static readonly double[] Special={0.0,-0.0,1.0,-1.0,double.NaN,double.PositiveInfinity,double.NegativeInfinity,double.MaxValue,-double.MaxValue,double.Epsilon,1e-40,1.0000000596046448};
 static object Transfer(Assembly a,int nx,int ny,int ns,int sg,int workers) {
  var action=P.GetMethod("TransferConcentrations",F).CreateDelegate<Action>();((ParallelOptions)Get("pOptions")).MaxDegreeOfParallelism=workers;var d=DG(nx,ny,ns,sg);var f=FG(nx,ny,ns,sg);Set("Conz3dDouble",d);Set("Conz3d",f);Set("NS",ns);Set("SourceGroups",Enumerable.Range(1,sg).ToList());
  long total=0;foreach(var x in d)foreach(var y in x)foreach(var z in y)for(int q=0;q<z.Length;q++)z[q]=Special[total++%Special.Length];action();long checkedValues=0;
  for(int i=0;i<nx;i++)for(int j=0;j<ny;j++)for(int k=0;k<ns;k++)for(int q=0;q<sg;q++){float expected=(float)Special[checkedValues++%Special.Length];if(BitConverter.SingleToInt32Bits(f[i][j][k][q])!=BitConverter.SingleToInt32Bits(expected)||BitConverter.DoubleToInt64Bits(d[i][j][k][q])!=0)throw new Exception("Transfer cast or reset");}
  var warm=Stopwatch.StartNew();int warmCalls=0;while(warm.Elapsed.TotalMilliseconds<750||warmCalls<8){action();warmCalls++;}
  warm.Stop();
  var times=new List<double>();for(int r=0;r<15;r++){foreach(var x in d)foreach(var y in x)foreach(var z in y)Array.Fill(z,1.25);var sw=Stopwatch.StartNew();for(int t=0;t<5;t++)action();sw.Stop();times.Add(sw.Elapsed.TotalMilliseconds/5);}
  return new{status="pass",scope="Actual private TransferConcentrations via delegate; exact cast bits and double reset including NaN, infinity and signed zero",nx,ny,slices=ns,source_groups=sg,workers,warmup_calls=warmCalls,warmup_ms=warm.Elapsed.TotalMilliseconds,checked_values=checkedValues,elapsed_ms_per_transfer=times,timing_note="Warm method; first transfer in each batch has nonzero doubles, subsequent four have zeros; same loop touches all entries in both versions. Fill and allocation excluded."};
 }
 static void Main(string[] args){var a=Assembly.LoadFrom(Path.GetFullPath(args[0]));P=a.GetType("GRAL_2001.Program");object result=args[1]=="allocation"?Allocation(a,args[2]=="reuse"):args[1]=="initialize"?Initialize(a):Transfer(a,int.Parse(args[2]),int.Parse(args[3]),int.Parse(args[4]),int.Parse(args[5]),int.Parse(args[6]));File.WriteAllText(args[^1],JsonSerializer.Serialize(result,new JsonSerializerOptions{WriteIndented=true})+"\n");}
}
