from pathlib import Path
import shutil
root=Path(__file__).resolve().parent
probe=r'''using System;
using System.Reflection;
using System.Threading;
namespace GRAL_2001 {
 public static class WorkerDriverProbe {
  public static int[] Visits; public static int NullBuffers;
  public static void Visit(int particle,double[] buffer) {
   Interlocked.Increment(ref Visits[particle]);if(buffer==null)Interlocked.Increment(ref NullBuffers);
   int q=particle%Program.SourceGroups.Count;double value=particle/1024.0;
   int slot=-1,ny=0,ns=0,nslots=0;
   if(buffer!=null){Type p=typeof(Program);var flags=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Static;slot=((int[])p.GetField("WorkerConcentrationSlots",flags).GetValue(null))[q];ny=(int)p.GetField("WorkerConcentrationNy",flags).GetValue(null);ns=(int)p.GetField("WorkerConcentrationNs",flags).GetValue(null);nslots=(int)p.GetField("WorkerConcentrationSlotCount",flags).GetValue(null);}
   if(slot>=0)buffer[((1*ny+1)*ns)*nslots+slot]+=value;
   else{double[] target=Program.Conz3dDouble[1][1][0];lock(target){target[q]+=value;}}
  }
 }
}'''
for variant,source in [('f64',root/'source/f64/src'),('candidate',root/'repo/src')]:
 target=root/'probe'/variant/'src';target.parent.mkdir(parents=True);shutil.copytree(source,target)
 p=target/'Zeitschleife.cs';s=p.read_text(encoding='utf-8-sig');signature='internal static void CalculateWithWorkerBuffer(int nteil, double[] workerConcentration)' if variant=='candidate' else 'public static void Calculate(int nteil)';start=s.index(signature);left=s.index('{',start);depth=1;i=left+1
 while depth:
  if s[i]=='{':depth+=1
  elif s[i]=='}':depth-=1
  i+=1
 replacement='{\n            WorkerDriverProbe.Visit(nteil, '+('workerConcentration' if variant=='candidate' else 'null')+');\n        }';p.write_text(s[:left]+replacement+s[i:],encoding='utf-8-sig');(target/'WorkerDriverProbe.cs').write_text(probe,encoding='utf-8')
fixture=root/'driver_fixture';fixture.mkdir()
cs=r'''using System;
using System.Reflection;
using System.Collections.Generic;
using System.Text.Json;
using System.Threading.Tasks;
class DriverFixture {
 static Type P;static object Get(string n)=>P.GetField(n,BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Static).GetValue(null);static void Set(string n,object value)=>P.GetField(n,BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Static).SetValue(null,value);
 static void Check(bool ok,string message){if(!ok)throw new Exception(message);}
 static double[][][][] Field(){var a=new double[3][][][];for(int i=0;i<3;i++){a[i]=new double[4][][];for(int j=0;j<4;j++){a[i][j]=new double[2][];for(int k=0;k<2;k++){a[i][j][k]=new double[5];for(int g=0;g<5;g++)a[i][j][k][g]=g+.125;}}}return a;}
 static void Main(string[] args){Environment.SetEnvironmentVariable("GRAL_WORKER_CONCENTRATION_MB",args[1]);var a=Assembly.LoadFrom(args[0]);P=a.GetType("GRAL_2001.Program");var probe=a.GetType("GRAL_2001.WorkerDriverProbe");int workers=int.Parse(args[2]),lower=int.Parse(args[3]),upper=int.Parse(args[4]);((ParallelOptions)Get("pOptions")).MaxDegreeOfParallelism=workers;Set("UseFixedRndSeedVal",true);Set("SourceGroups",new List<int>{42,7,255,1,88});Set("Conz3dDouble",Field());Set("NTEILMAX",upper-1);Set("PS_Count",2);Set("PS_SG",new byte[]{0,7,88});Set("PS_PartNumb",new int[]{0,100,0});Set("LS_Count",1);Set("LS_SG",new byte[]{0,1});Set("LS_PartNumb",new int[]{0,50});Set("TS_Count",1);Set("TS_SG",new byte[]{0,255});Set("TS_PartNumb",new int[]{0,10});Set("AS_Count",1);Set("AS_SG",new byte[]{0,42});Set("AS_PartNumb",new int[]{0,0});var visits=new int[upper+1];probe.GetField("Visits").SetValue(null,visits);P.GetMethod("ParallelParticleDriver",BindingFlags.NonPublic|BindingFlags.Static).Invoke(null,new object[]{lower,upper});for(int i=0;i<visits.Length;i++)Check(visits[i]==(i>=lower&&i<upper?1:0),"visit coverage "+i);
 var expected=new double[5];for(int q=0;q<5;q++)expected[q]=q+.125;for(int i=lower;i<upper;i++)expected[i%5]+=i/1024.0;var actual=((double[][][][])Get("Conz3dDouble"))[1][1][0];for(int q=0;q<5;q++)Check(BitConverter.DoubleToInt64Bits(expected[q])==BitConverter.DoubleToInt64Bits(actual[q]),"group sum "+q);int noBuffer=(int)probe.GetField("NullBuffers").GetValue(null);bool supports=P.GetField("WorkerConcentrations",BindingFlags.NonPublic|BindingFlags.Static)!=null;bool buffered=supports&&args[1]=="1"&&workers>1;Check(noBuffer==(buffered?0:upper-lower),"buffer ownership");Console.WriteLine("[DRIVER] "+JsonSerializer.Serialize(new{status="pass",workers,lower,upper,particles=upper-lower,buffered,unbuffered_calls=noBuffer,group_sums=actual}));
 }
}'''
(fixture/'DriverFixture.cs').write_text(cs,encoding='utf-8');(fixture/'DriverFixture.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>\n');print('instrumented driver coverage sources prepared, not built')
