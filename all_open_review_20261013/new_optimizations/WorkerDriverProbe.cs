using System;
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
}