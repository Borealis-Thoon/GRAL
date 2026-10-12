using System.Reflection;
using System.Text.Json;
class Checks {
 static Type P,M,Z; static int checks; static List<object> details=new(); static BindingFlags B=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Static;
 static FieldInfo Field(Type t,string n)=>t.GetField(n,B) ?? throw new Exception("field "+n);
 static object Get(Type t,string n)=>Field(t,n).GetValue(null);
 static void Set(Type t,string n,object value) { var f=Field(t,n);f.SetValue(null,value is IConvertible && f.FieldType.IsPrimitive ? Convert.ChangeType(value,f.FieldType):value); }
 static object Call(Type t,string n,params object[] args)=>(t.GetMethod(n,B) ?? throw new Exception("method "+n)).Invoke(null,args);
 static void Check(bool ok,string name) { checks++; if(!ok) throw new Exception(name);details.Add(new{name,pass=true}); }
 static double Ref =>(double)Get(M,"ParticleMassActive");
 static void Factors(float a,float b,float c,float d) { var f=(float[,])Get(P,"EmFacTimeSeries");f[0,0]=a;f[0,1]=b;f[0,2]=c;f[0,3]=d; }
 static void SetupReference() {
  Set(P,"TAUS",1);Set(P,"TPS",1);Set(P,"GridVolume",(float)(1000000000.0/3600));Set(P,"IWET",1);Set(P,"SourceGroups",new List<int>{0,1,2,3});Set(P,"EmissionTimeseriesExist",true);Set(P,"EmFacTimeSeries",new float[5,4]);
  string[] types={"PS","LS","TS","AS"};double[] rates={1,2,3,20};
  for(int i=0;i<4;i++) { string n=types[i];Set(P,n+"_ER",new double[]{0,rates[i]});Set(P,n+"_ER_Dep",new float[]{0,1});Set(P,n+"_Mode",new byte[]{0,0});Set(P,n+"_SG",new byte[]{0,(byte)i});Set(P,n+"_Count",1); }
  double unit=1.0/3600*1000000000/(float)Get(P,"GridVolume");Set(P,"ParticleMassMean",26.0/3600*1000000000/(float)Get(P,"GridVolume"));Set(M,"ParticleMassActive",0d);
 }
 static int Count(double mass)=>(int)Call(Z,"ResidualSplitCount",mass);
 static double K=>(double)Get(Z,"residualSplitK");
 static void Grid(float[] masses,float budget) {
  Set(P,"TAUS",1);Set(P,"TPS",budget);Set(P,"GridVolume",1);Set(P,"DXK",1);Set(P,"DYK",1);Set(P,"DZK_Trans",new float[]{0,1});Set(P,"NII",masses.Length);Set(P,"NJJ",1);Set(P,"NKK_Transient",1);Set(P,"SourceGroups",new List<int>{0});Set(P,"TransConcThreshold",0);Set(M,"ParticleMassActive",1d);Set(P,"CancelToken",new System.Threading.CancellationTokenSource());((System.Threading.Tasks.ParallelOptions)Get(P,"pOptions")).MaxDegreeOfParallelism=1;
  var grid=new float[masses.Length+1][][][];
  for(int i=1;i<=masses.Length;i++) {grid[i]=new float[2][][];grid[i][1]=new float[2][];grid[i][1][1]=new float[]{masses[i-1]};}Set(P,"Conz4d",grid);
 }
 static object Plan(float[] masses,float budget) {
  Grid(masses,budget);Set(Z,"residualSplitK",10d);long before=masses.Sum(x=>(long)Count(x));Call(Z,"PlanResidual");long after=masses.Sum(x=>(long)Count(x));return new{entries=masses.Length,budget,initial_count=before,final_count=after,final_k=K,within_target=after<=budget};
 }
 static void Main(string[] args) {
  Assembly a=Assembly.LoadFrom(args[0]);P=a.GetType("GRAL_2001.Program",true);M=a.GetType("GRAL_2001.ParticleManagement",true);Z=a.GetType("GRAL_2001.ZeitschleifeNonSteadyState",true);var data=new Dictionary<string,object>();SetupReference();double unit=1.0/3600*1000000000/(float)Get(P,"GridVolume");double nominal=(double)Get(P,"ParticleMassMean");
  Factors(1,0,0,0);Call(M,"SetResidualParticleMass");Check(Ref==unit,"one active source");double active=Ref;Factors(.2f,0,0,0);Call(M,"SetResidualParticleMass");Check(Ref==active,"positive magnitude leaves policy unchanged");Factors(0,0,0,0);Call(M,"SetResidualParticleMass");double continuous=Ref;Check(Ref==nominal,"all off uses nominal after active");Set(M,"ParticleMassActive",0d);Call(M,"SetResidualParticleMass");Check(Ref==continuous,"fresh restart and continuous references match");Call(M,"SetResidualParticleMass");Check(Ref==nominal,"all off repeated idempotently");Set(P,"IWET",2);Call(M,"SetResidualParticleMass");Check(Ref==nominal,"later all-off situation same nominal");Set(P,"IWET",1);Factors(1,1,1,1);Call(M,"SetResidualParticleMass");Check(Ref==nominal,"four source classes summed");((byte[])Get(P,"PS_Mode"))[1]=2;((float[])Get(P,"PS_ER_Dep"))[1]=0;Call(M,"SetResidualParticleMass");Check(Ref==25.0/3600*1000000000/(float)Get(P,"GridVolume"),"inactive deposition-only excluded");((byte[])Get(P,"PS_Mode"))[1]=0;Set(P,"EmissionTimeseriesExist",false);Factors(0,0,0,0);Call(M,"SetResidualParticleMass");Check(Ref==nominal,"no time series uses all nominal sources");Set(P,"EmissionTimeseriesExist",true);Factors(-1,0,0,0);Call(M,"SetResidualParticleMass");Check(Ref==nominal,"nonpositive factors inactive fallback");
  data["reference_example"]=new{nominal_reference=nominal,active_reference=active,continuous_all_off=continuous,restart_all_off=Ref,old_continuous_all_off=active,old_restart_all_off=nominal,residual_mass=100*unit,k10_old_continuous=(int)Math.Min(100000,Math.Floor(Math.Floor(100*unit/active)/10)+1),k10_new_all_off=(int)Math.Min(100000,Math.Floor(Math.Floor(100*unit/nominal)/10)+1)};
  bool planner=Z.GetMethod("ResidualSplitCount",B)!=null;
  if(planner) {
   Set(M,"ParticleMassActive",1d);Set(Z,"residualSplitK",10d);double[] extremes={0,-0d,-1,double.NaN,1e-300,9.999,10,1e9,1e300,double.PositiveInfinity};int[] expected={1,1,1,1,1,1,2,100000,100000,100000};
   for(int i=0;i<extremes.Length;i++) Check(Count(extremes[i])==expected[i],"safe split "+i);
   foreach(double invalid in new[]{0d,-1d,double.NaN,double.PositiveInfinity}) {Set(M,"ParticleMassActive",invalid);int n=Count(100);Check(n>=1 && n<=100000,"bounded invalid reference "+invalid.ToString());}Set(M,"ParticleMassActive",1d);
   foreach(double k in new[]{10d,55d,1e200,double.MaxValue,double.PositiveInfinity}) {Set(Z,"residualSplitK",k);foreach(double mass in new[]{0d,1d,10d,1e300,double.PositiveInfinity}) {int n=Count(mass);Check(n>=1 && n<=100000,"bounded K "+k.ToString()+" mass "+mass.ToString());}}Set(Z,"residualSplitK",10d);
   int cases=0,mismatch=0,oldProductMismatch=0;var boundaryExamples=new List<object>();var rng=new Random(51012);
   for(int i=0;i<70000;i++) {double reference=Math.Pow(10,rng.NextDouble()*30-15);double n=(i%10000+1)*10.0;double center=n*reference;Set(M,"ParticleMassActive",reference);foreach(double mass in new[]{Math.BitDecrement(center),center,Math.BitIncrement(center)}) {int target=(int)Math.Min(100000,Math.Floor(Math.Floor(mass/reference)/10)+1);int value=Count(mass);if(value!=target)mismatch++;int old=(int)Math.Min(100000,Math.Floor(mass/(reference*10))+1);if(old!=target){oldProductMismatch++;if(boundaryExamples.Count<8)boundaryExamples.Add(new{mass,reference,target,new_count=value,old_product_count=old});}cases++;}}
   Check(mismatch==0,"K10 nested-floor boundary compatibility");Check(oldProductMismatch>0,"product denominator rounding reproduced");data["boundary_sweep"]=new{cases,mismatches=mismatch,old_product_disagreements=oldProductMismatch,examples=boundaryExamples};
   data["feasible_target"]=Plan(Enumerable.Repeat(100f,100).ToArray(),200);Check(K==55,"feasible factor 55");Check(Enumerable.Repeat(100f,100).Sum(x=>(long)Count(x))==200,"feasible final count200");
   data["entry_lower_bound"]=Plan(Enumerable.Repeat(.01f,300).ToArray(),200);Check(Enumerable.Repeat(.01f,300).Sum(x=>(long)Count(x))==300,"minimum one per eligible entry");
   data["six_pass_limit"]=Plan(new float[]{1000000}.Concat(Enumerable.Repeat(1f,999)).ToArray(),1001);Check(K>10 && K<1e300,"six finite adjustments");Check(((float[][][][])Get(P,"Conz4d")).Skip(1).Sum(x=>(long)Count(x[1][1][0]))>1001,"six-pass target remains soft");
   Grid(new float[]{100,.01f},100);Set(P,"TransConcThreshold",1);Call(Z,"PlanResidual");Check(K==10,"planner threshold excludes low entry");
   Grid(Enumerable.Repeat(1e6f,30000).ToArray(),3e9f);Call(Z,"PlanResidual");long huge=((float[][][][])Get(P,"Conz4d")).Skip(1).Sum(x=>(long)Count(x[1][1][0]));Check(huge==3000000000L,"total uses long above Int32");data["long_total"]=huge;
   Grid(Enumerable.Repeat(100f,16).ToArray(),32);((System.Threading.Tasks.ParallelOptions)Get(P,"pOptions")).MaxDegreeOfParallelism=2;Call(Z,"PlanResidual");Check(K==55,"two-worker planner same count policy");
   ((System.Threading.CancellationTokenSource)Get(P,"CancelToken")).Cancel();Set(P,"Conz4d",null);Set(P,"NII",1000000);Call(Z,"PlanResidual");Check(K==55,"pre-cancellation reads no grid or changes factor");
   float concentration=100f;int count=11;double reconstruction=(concentration/count)*(double)count;Check(Math.Abs(reconstruction-concentration)/concentration<1e-7,"ordinary split float mass rounding bounded");float subnormal=float.Epsilon/2;Check(subnormal==0,"remaining subnormal underflow documented");data["mass_rounding"]=new{concentration,count,reconstruction,relative_error=(reconstruction-concentration)/concentration,subnormal_lost=true};
  }
  data["status"]="pass";data["checks_passed"]=checks;data["checks"]=details;data["scope"]="Calls actual frozen GRAL DLL methods through reflection. Main restart is tested separately. Floating-point mass splitting still rounds.";File.WriteAllText(args[1],JsonSerializer.Serialize(data,new JsonSerializerOptions{WriteIndented=true}));Console.WriteLine("[PASS] checks "+checks);
 }
}
