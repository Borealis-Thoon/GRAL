using System;
using System.IO;
using System.Reflection;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
class Fixture {
 static Type P; static Assembly A; static int assertions;
 static object Get(string n)=>P.GetField(n,BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Static).GetValue(null);
 static void Set(string n,object v)=>P.GetField(n,BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Static).SetValue(null,v);
 static object Call(string n,params object[] a)=>P.GetMethod(n,BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Static).Invoke(null,a);
 static void Check(bool ok,string label){assertions++;if(!ok)throw new Exception(label);}
 static float[][][][] FloatField(int nx,int ny,int ns,int ng){var a=new float[nx][][][];for(int i=0;i<nx;i++){a[i]=new float[ny][][];for(int j=0;j<ny;j++){a[i][j]=new float[ns][];for(int k=0;k<ns;k++)a[i][j][k]=new float[ng];}}return a;}
 static double[][][][] Field(int nx=3,int ny=4,int ns=2,int ng=5){var a=new double[nx][][][];for(int i=0;i<nx;i++){a[i]=new double[ny][][];for(int j=0;j<ny;j++){a[i][j]=new double[ns][];for(int k=0;k<ns;k++){a[i][j][k]=new double[ng];for(int g=0;g<ng;g++)a[i][j][k][g]=g+.125;}}}return a;}
 static void Configure(int workers=4){((ParallelOptions)Get("pOptions")).MaxDegreeOfParallelism=workers;Set("UseFixedRndSeedVal",true);Set("SourceGroups",new List<int>{42,7,255,1,88});Set("Conz3dDouble",Field());Set("PS_Count",2);Set("PS_SG",new byte[]{0,7,88});Set("PS_PartNumb",new int[]{0,100,0});Set("LS_Count",1);Set("LS_SG",new byte[]{0,1});Set("LS_PartNumb",new int[]{0,50});Set("TS_Count",1);Set("TS_SG",new byte[]{0,255});Set("TS_PartNumb",new int[]{0,10});Set("AS_Count",1);Set("AS_SG",new byte[]{0,42});Set("AS_PartNumb",new int[]{0,0});}
 static void MergeCheck(int[] expectedSlots){var slots=(int[])Get("WorkerConcentrationSlots");Check(slots.SequenceEqual(expectedSlots),"slot mapping");var buffers=(double[][])Get("WorkerConcentrations");var field=(double[][][][])Get("Conz3dDouble");int nslots=(int)Get("WorkerConcentrationSlotCount");int workers=((ParallelOptions)Get("pOptions")).MaxDegreeOfParallelism;
 var expected=Field();for(int i=0;i<3;i++)for(int j=0;j<4;j++)for(int s=0;s<2;s++)for(int q=0;q<5;q++)expected[i][j][s][q]=field[i][j][s][q];
 for(int w=0;w<workers;w++)for(int i=0;i<3;i++)for(int j=0;j<4;j++)for(int s=0;s<2;s++)for(int q=0;q<5;q++)if(slots[q]>=0){double value=(w+1)*(q+1)/16.0;buffers[w][((i*4+j)*2+s)*nslots+slots[q]]=value;expected[i][j][s][q]+=value;}
 Call("MergeWorkerConcentrations");for(int i=0;i<3;i++)for(int j=0;j<4;j++)for(int s=0;s<2;s++)for(int q=0;q<5;q++)Check(BitConverter.DoubleToInt64Bits(field[i][j][s][q])==BitConverter.DoubleToInt64Bits(expected[i][j][s][q]),"residual plus worker sums");foreach(var b in buffers)foreach(double value in b)Check(value==0,"buffer clear");}
 static void InactiveParticleCheck(){
 Set("SourceGroups",new List<int>{1,2});Set("WorkerConcentrationSlots",new[]{0,1});
 foreach(string name in new[]{"Xcoord","YCoord","ZCoord","ParticleMass","ParticleMode","ParticleVsed","ParticleVdep","ParticleSource"}){var field=P.GetField(name,BindingFlags.Public|BindingFlags.Static);field.SetValue(null,Array.CreateInstance(field.FieldType.GetElementType(),3));}
 Set("ParticleSG",new byte[]{0,255,255});Set("DDX",new float[]{0,1});Set("DDY",new float[]{0,1});
 var z=A.GetType("GRAL_2001.Zeitschleife");var buffered=z.GetMethod("CalculateWithWorkerBuffer",BindingFlags.NonPublic|BindingFlags.Static);var legacy=z.GetMethod("Calculate",BindingFlags.Public|BindingFlags.Static);
 for(int particle=1;particle<=2;particle++){buffered.Invoke(null,new object[]{particle,new double[16]});Check(true,"inactive particle returns before poisoned SG buffer lookup "+particle);legacy.Invoke(null,new object[]{particle});Check(true,"public inactive particle call "+particle);}
 }
 static void Main(string[] args){Environment.SetEnvironmentVariable("GRAL_WORKER_CONCENTRATION_MB",args[1]);A=Assembly.LoadFrom(args[0]);P=A.GetType("GRAL_2001.Program");Configure();var z=A.GetType("GRAL_2001.Zeitschleife");Check(z.GetMethods(BindingFlags.Public|BindingFlags.Static).Count(m=>m.Name=="Calculate")==1,"unique public Calculate");Check(z.GetMethod("Calculate",new[]{typeof(int)})!=null,"original Calculate signature");
 long budget=(long)Get("WorkerConcentrationBudget");bool enabled=(bool)Call("PrepareWorkerConcentrations");var tests=new List<string>();
 if(budget==0){Check(!enabled && Get("WorkerConcentrations")==null,"off no allocation");tests.Add("off");}
 else {
 Check(enabled,"enabled");MergeCheck(new[]{-1,0,1,2,-1});var first=(double[][])Get("WorkerConcentrations");tests.Add("all four source kinds mapped; absent group retains residual sum");
 Set("PS_PartNumb",new int[]{0,0,0});Set("AS_PartNumb",new int[]{0,10});Check((bool)Call("PrepareWorkerConcentrations"),"mapping update");Check(ReferenceEquals(first,Get("WorkerConcentrations")),"reuse allocation");MergeCheck(new[]{0,-1,1,2,-1});tests.Add("same-capacity group-map change");
 Set("PS_PartNumb",new int[]{0,100,0});Check(!(bool)Call("PrepareWorkerConcentrations"),"growth fallback");Check(ReferenceEquals(first,Get("WorkerConcentrations")),"growth did not allocate");tests.Add("capacity fallback");Set("PS_PartNumb",new int[]{0,0,0});Check((bool)Call("PrepareWorkerConcentrations"),"reuse after growth fallback");Check(ReferenceEquals(first,Get("WorkerConcentrations")),"same cache after fallback");MergeCheck(new[]{0,-1,1,2,-1});tests.Add("smaller mapping after growth fallback");Set("PS_PartNumb",new int[]{0,100,0});
 Set("Conz3dDouble",Field(128,128,2));Check(!(bool)Call("PrepareWorkerConcentrations"),"budget or capacity fallback");Check(ReferenceEquals(first,Get("WorkerConcentrations")),"budget did not allocate");tests.Add("large required storage fallback");
 Set("Conz3dDouble",Field());((ParallelOptions)Get("pOptions")).MaxDegreeOfParallelism=1;Check(!(bool)Call("PrepareWorkerConcentrations"),"one worker fallback");((ParallelOptions)Get("pOptions")).MaxDegreeOfParallelism=4;Set("UseFixedRndSeedVal",false);Check(!(bool)Call("PrepareWorkerConcentrations"),"random driver fallback");tests.Add("one-worker and non-fixed-seed driver fallback");
 Set("UseFixedRndSeedVal",true);Set("PS_PartNumb",new int[]{0,0,0});Set("LS_PartNumb",new int[]{0,0});Set("TS_PartNumb",new int[]{0,0});Set("AS_PartNumb",new int[]{0,0});Check(!(bool)Call("PrepareWorkerConcentrations"),"no allocated groups fallback");tests.Add("no allocated groups fallback");
 }
 InactiveParticleCheck();
 Console.WriteLine("[FIXTURE] "+JsonSerializer.Serialize(new{status="pass",budget_bytes=budget,assertions,tests}));}
}