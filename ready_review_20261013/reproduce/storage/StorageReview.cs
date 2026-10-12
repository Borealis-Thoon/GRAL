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
class StorageReview
{
 const BindingFlags F=BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic;
 static int checks;
 static readonly Dictionary<string,int> groups=new();
 static void Check(bool ok,string group) { if(!ok)throw new Exception(group); Interlocked.Increment(ref checks); lock(groups)groups[group]=groups.GetValueOrDefault(group)+1; }
 sealed class Model
 {
  public readonly Type P,T; public readonly Dictionary<string,MethodInfo> Methods;
  public Model(string path) { var a=new AssemblyLoadContext(Guid.NewGuid().ToString(),false).LoadFromAssemblyPath(Path.GetFullPath(path));P=a.GetType("GRAL_2001.Program",true);T=a.GetType("GRAL_2001.TransientConcentration",true);Methods=new[]{"Conz5dZeitschleife","Conz5dZeitschleifeTransient"}.ToDictionary(n=>n,n=>T.GetMethod(n,F)); }
  public void Set(string name,object value) { var f=P.GetField(name,F);f.SetValue(null,f.FieldType.IsInstanceOfType(value)?value:Convert.ChangeType(value,f.FieldType)); }
  public float[][][][] Grid;
  public void Reset(float initial=0) { Grid=Enumerable.Range(0,4).Select(_=>Enumerable.Range(0,4).Select(_=>Enumerable.Range(0,5).Select(_=>new float[]{initial,17}).ToArray()).ToArray()).ToArray();Set("DXK",20);Set("DYK",20);Set("GridVolume",1);Set("TAUS",1);Set("NKK_Transient",3);Set("HoKartTrans",new float[]{0,10,20,30,40});Set("DZK_Trans",new float[]{1,1,1,1,1});Set("Conz5d",Grid);T.GetField("NonFiniteResidualWriteCount",F)?.SetValue(null,0L); }
  public long Counter => (long)T.GetField("NonFiniteResidualWriteCount",F).GetValue(null);
  public void Call(string n,double mass,double x=1,double y=1,float z=1,float h=0,double area=1,int r=0,int sg=0) => Methods[n].Invoke(null,new object[]{r,z,h,mass,area,.1f,x,y,sg});
  public int[] Bits()=>Grid.SelectMany(x=>x.SelectMany(y=>y.SelectMany(z=>z))).Select(BitConverter.SingleToInt32Bits).ToArray();
 }
 static void Main(string[] args)
 {
  var reference=new Model(args[0]);var candidate=new Model(args[1]);var rnd=new Random(672026);int finitePairs=0,invalidCases=0;
  foreach(var n in candidate.Methods.Keys)
  {
   // Each case begins from the same float cells; negative finite mass is intentionally retained.
   var masses=new[]{-0d,0d,double.Epsilon,-double.Epsilon,1e-40,-1e-40,-1d,1d,1e20,-1e20}.Concat(Enumerable.Range(0,1000).Select(_=>(rnd.NextDouble()-.5)*1e10));
   foreach(double mass in masses) foreach(float z in new[]{.01f,10f,MathF.BitIncrement(10f),29.9f})
   {
    reference.Reset(3);candidate.Reset(3);
    foreach(var m in new[]{reference,candidate}) { m.Set("GridVolume",7);m.Set("TAUS",30);m.Set("DZK_Trans",new float[]{1,10,7,4,1});m.Call(n,mass,z:z,area:400); }
    Check(candidate.Bits().SequenceEqual(reference.Bits()),"finite_signed_mass_bitwise");Check(candidate.Counter==0,"finite_signed_mass_no_rejection");finitePairs++;
   }
   foreach(double bad in new[]{double.NaN,double.PositiveInfinity,double.NegativeInfinity})
   foreach(string field in new[]{"x","y","mass","z","surface"})
   {
    candidate.Reset(3);var before=candidate.Bits();candidate.Call(n,field=="mass"?bad:1,x:field=="x"?bad:1,y:field=="y"?bad:1,z:field=="z"?(float)bad:1,h:field=="surface"?(float)bad:0);
    Check(before.SequenceEqual(candidate.Bits()),"invalid_input_preserves_all_cells");Check(candidate.Counter==1,"invalid_input_count_once");invalidCases++;
   }
   foreach(string fault in new[]{"relative_height_overflow","zero_area","nan_area","infinite_contribution","zero_thickness","nonfinite_tau"})
   {
    candidate.Reset(3);var before=candidate.Bits();
    if(fault=="zero_thickness")candidate.Set("DZK_Trans",new float[5]);if(fault=="nonfinite_tau")candidate.Set("TAUS",float.PositiveInfinity);
    candidate.Call(n,fault=="infinite_contribution"?double.MaxValue:1,z:fault=="relative_height_overflow"?float.MaxValue:1,h:fault=="relative_height_overflow"?-float.MaxValue:0,area:fault=="zero_area"?0:fault=="nan_area"?double.NaN:1);
    Check(before.SequenceEqual(candidate.Bits()),"derived_nonfinite_preserves_all_cells");Check(candidate.Counter==1,"derived_nonfinite_count_once");invalidCases++;
   }
   foreach(float initial in new[]{float.MaxValue,-float.MaxValue})
   {
    candidate.Reset(initial);var before=candidate.Bits();candidate.Call(n,initial);Check(before.SequenceEqual(candidate.Bits()),"signed_total_overflow_preserves_all_cells");Check(candidate.Counter==1,"signed_total_overflow_count_once");invalidCases++;
   }
   foreach(float polluted in new[]{float.NaN,float.PositiveInfinity,float.NegativeInfinity,BitConverter.Int32BitsToSingle(unchecked((int)0x7FC01234))})
   {
    candidate.Reset(0);candidate.Grid[1][1][1][0]=polluted;var before=candidate.Bits();candidate.Call(n,1);
    Check(candidate.Bits().SequenceEqual(before),"preexisting_nonfinite_preserved_not_repaired");Check(candidate.Counter==1,"preexisting_nonfinite_write_count");
    candidate.Call(n,2,sg:1);Check(candidate.Grid[1][1][1][1]==19,"other_source_group_unaffected");
   }
   candidate.Reset(3);var untouched=candidate.Bits();candidate.Call(n,double.NaN,x:double.NaN,r:1,sg:int.MaxValue);Check(candidate.Bits().SequenceEqual(untouched)&&candidate.Counter==0,"reflected_call_noop_before_addressing");
   foreach(int workers in new[]{1,2,8})
   {
    candidate.Reset();Parallel.For(0,4096,new ParallelOptions{MaxDegreeOfParallelism=workers},i=>candidate.Call(n,i%2==0?1:double.NaN));
    Check(candidate.Grid[1][1][1][0]==2048,"same_cell_parallel_finite_sum");Check(candidate.Counter==2048,"same_cell_parallel_invalid_count");
    candidate.Reset();Parallel.For(0,4096,new ParallelOptions{MaxDegreeOfParallelism=workers},i=>candidate.Call(n,i%2==0?1:-1));
    Check(candidate.Grid[1][1][1][0]==0,"same_cell_signed_exact_sum");Check(candidate.Counter==0,"same_cell_signed_not_rejected");
    candidate.Reset();float contribution=float.MaxValue*.75f;Parallel.For(0,64,new ParallelOptions{MaxDegreeOfParallelism=workers},_=>candidate.Call(n,contribution));
    Check(candidate.Grid[1][1][1][0]==contribution,"same_cell_overflow_one_survives");Check(candidate.Counter==63,"same_cell_overflow_rejected_count");
   }
  }
  var result=new{status="pass",checks,groups,finite_bitwise_pairs=finitePairs,invalid_write_cases=invalidCases,parallel_workers=new[]{1,2,8},scope="Actual baseline and candidate DLL storage methods. Finite signed mass preservation, non-finite write rejection, destination overflow, and concurrent same-cell writes. Existing non-finite cells remain unchanged; finite invalid domain indices and malformed grid dimensions remain outside this patch. No Main fault injection or performance claim.",dlls=args.Take(2).Select(p=>new{path=p,sha256=Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(p)))})};
  File.WriteAllText(args[2],JsonSerializer.Serialize(result,new JsonSerializerOptions{WriteIndented=true}));Console.WriteLine(JsonSerializer.Serialize(new{status="pass",checks,finitePairs,invalidCases}));
 }
}
