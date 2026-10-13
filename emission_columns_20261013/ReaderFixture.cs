using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Globalization;
using System.Text.Json;
namespace GRAL_2001 {
public static class Consts { public const int TransientMode = 0; }
public static class Program {
 public static int ISTATIONAER = 0;
 public static List<int> SourceGroups = new List<int>();
 public static bool EmissionTimeseriesExist;
 public static float[,] EmFacTimeSeries = new float[0,0];
 public static int Get_Internal_SG_Number(int sg) => SourceGroups.IndexOf(sg);
}
public partial class ProgramReaders { public static string decsep = "."; }
public static class ProgramWriters { public static void LogfileGralCoreWrite(string info) {} }
public record TestCase(string Name, int[] Groups, string Text, float[][] Expected, bool Defect);
public class Entry {
 public static void Main(string[] args) {
  CultureInfo.CurrentCulture = CultureInfo.InvariantCulture;
  var cases = new List<TestCase> {
   new("figure_selected_one",new[]{1},"date;hour;2;1\n01.01.2022;00;4;0.5\n01.01.2022;01;4;2\n01.01.2022;02;4;1\n",new[]{new[]{.5f},new[]{2f},new[]{1f}},true),
   new("matched",new[]{1,2},"date;hour;1;2\n01.01.2022;00;1;2\n01.01.2022;01;0;0.5\n01.01.2022;02;3;4\n",new[]{new[]{1f,2f},new[]{0f,.5f},new[]{3f,4f}},false),
   new("reordered",new[]{2,1},"date;hour;1;2\n01.01.2022;00;1;2\n01.01.2022;01;0;0.5\n",new[]{new[]{2f,1f},new[]{.5f,0f}},false),
   new("extra_first",new[]{1,2},"date;hour;99;1;2\n01.01.2022;00;9;1;2\n01.01.2022;01;9;0;0.5\n",new[]{new[]{1f,2f},new[]{0f,.5f}},true),
   new("extra_middle",new[]{1,2},"date;hour;1;99;2\n01.01.2022;00;1;9;2\n01.01.2022;01;0;9;0.5\n",new[]{new[]{1f,2f},new[]{0f,.5f}},true),
   new("extra_last",new[]{1,2},"date;hour;1;2;99\n01.01.2022;00;1;2;9\n01.01.2022;01;0;0.5;9\n",new[]{new[]{1f,2f},new[]{0f,.5f}},true),
   new("selected_after_many",new[]{7},"date;hour;1;2;3;7\n01.01.2022;00;8;9;2;0.25\n01.01.2022;01;8;9;2;2.5\n",new[]{new[]{.25f},new[]{2.5f}},true),
   new("selected_absent",new[]{1,2},"date;hour;1\n01.01.2022;00;0.25\n01.01.2022;01;2.5\n",new[]{new[]{.25f,1f},new[]{2.5f,1f}},false),
   new("all_unselected",new[]{1,2},"date;hour;98;99\n01.01.2022;00;4;5\n01.01.2022;01;6;7\n",new[]{new[]{1f,1f},new[]{1f,1f}},true),
   new("missing_selected_value",new[]{1,2},"date;hour;1;2\n01.01.2022;00;0.25\n01.01.2022;01;2.5;0.5\n",new[]{new[]{.25f,1f},new[]{2.5f,.5f}},false),
   new("missing_after_unselected",new[]{1,2},"date;hour;99;1;2\n01.01.2022;00;8;0.25\n01.01.2022;01;8;2.5;0.5\n",new[]{new[]{.25f,1f},new[]{2.5f,.5f}},true),
   new("ignored_text_value",new[]{1,2},"date;hour;99;1;2\n01.01.2022;00;unused;0.25;0.5\n01.01.2022;01;unused;2.5;0\n",new[]{new[]{.25f,.5f},new[]{2.5f,0f}},true),
   new("duplicate_selected",new[]{1,2,3},"date;hour;1;1;2\n01.01.2022;00;8;0.25;0.5\n01.01.2022;01;8;2.5;0\n",new[]{new[]{.25f,.5f,1f},new[]{2.5f,0f,1f}},false)
  };
  var records = new List<object>(); int asserts=0;
  foreach(var c in cases) {
   var d=Path.Combine(args[0],c.Name); Directory.CreateDirectory(d); Directory.SetCurrentDirectory(d);
   File.WriteAllText("emissions_timeseries.txt",c.Text);Program.SourceGroups=c.Groups.ToList();Program.EmissionTimeseriesExist=false;
   var old=Console.Out; using var capture=new StringWriter();Console.SetOut(capture);new ProgramReaders().ReadEmissionTimeseries();Console.SetOut(old);
   var actual=Enumerable.Range(0,c.Expected.Length).Select(i=>Enumerable.Range(0,c.Groups.Length).Select(g=>Program.EmFacTimeSeries[i,g]).ToArray()).ToArray();
   bool equal=actual.SelectMany(x=>x).SequenceEqual(c.Expected.SelectMany(x=>x));string log=capture.ToString();bool complete=log.Contains("Reading emissions_timeseries.txt successful");
   if(!Program.EmissionTimeseriesExist)throw new Exception("file not marked present");asserts++;
   if(args[1]=="candidate" || !c.Defect) { if(!equal||!complete)throw new Exception(c.Name+" result mismatch: "+log);asserts+=c.Expected.Length*c.Groups.Length+1; }
   else {if(equal && complete)throw new Exception(c.Name+" baseline failure not reproduced");asserts++;}
   if(args[1]=="candidate") {
    var header=c.Text.Split('\n')[0].Split(';').Skip(2).Select(int.Parse).ToArray();
    foreach(int sg in header.Distinct()) {
     int g=Array.IndexOf(c.Groups,sg);
     if(g<0) { if(log.Contains("Source group: "+sg+" "))throw new Exception("unused group logged");asserts++; }
     else if(header.Count(x=>x==sg)==1) {
      double mean=Math.Round(c.Expected.Average(row=>(double)row[g]),2);
      if(!log.Contains("Source group: "+sg+" Mean emission factor: "+mean.ToString(CultureInfo.InvariantCulture)))throw new Exception(c.Name+" mean mismatch "+log);asserts++;
     }
    }
   }
   records.Add(new{name=c.Name,known_defect=c.Defect,equal,complete,expected=c.Expected,actual,log});
  }
  File.WriteAllText(args[2],JsonSerializer.Serialize(new{status="pass",variant=args[1],cases=cases.Count,assertions=asserts,records},new JsonSerializerOptions{WriteIndented=true}));Console.WriteLine("[PASS] "+cases.Count+" cases "+asserts+" assertions");
 }
}
}