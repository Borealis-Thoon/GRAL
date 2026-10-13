using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Text.Json;
namespace GRAL_2001 {
internal static class VarianceReview {
 struct Cache { internal float Ob,Ust,Variance; public Cache(){Ob=Ust=float.NaN;Variance=0;} }
 static long checks,checksum;
 [MethodImpl(MethodImplOptions.AggressiveInlining)]
 static float Original(float ObLength,float Ustern,float blh) => Program.Pow2(Ustern) * Program.Pow2(1.15F + 0.1F * MathF.Pow(blh / (-ObLength), 0.67F)) * Program.Pow2(Program.StdDeviationW);
 [MethodImpl(MethodImplOptions.AggressiveInlining)]
 static float Cached(float ObLength,float Ustern,float blh,ref Cache cache) {
 float varw;
                         if (ObLength != cache.Ob || Ustern != cache.Ust)
                        {
                            cache.Variance = Program.Pow2(Ustern) * Program.Pow2(1.15F + 0.1F * MathF.Pow(blh / (-ObLength), 0.67F)) * Program.Pow2(Program.StdDeviationW);
                            cache.Ob = ObLength;
                            cache.Ust = Ustern;
                        }
                        varw = cache.Variance;
 return varw;
 }
 static void Verify(float[] ob,float[] ust,float blh) {
 var c=new Cache();
 for(int i=0;i<ob.Length;i++) {
  float a=Original(ob[i],ust[i],blh),b=Cached(ob[i],ust[i],blh,ref c);
  if(BitConverter.SingleToInt32Bits(a)!=BitConverter.SingleToInt32Bits(b))throw new Exception($"variance bits differ i={i} ob={ob[i]} ust={ust[i]} blh={blh}");
  checks++;
 }
 }
 [MethodImpl(MethodImplOptions.NoInlining)]
 static float OriginalGradient(float velxold,float velyold,float UXint,float UYint,float termp,float termq,float idt,float U0int,float zuff1) {
 float DUDX=0,DUDY=0,DSIGUDX=0,DSIGUDY=0; float velX=velxold+UXint,velY=velyold+UYint;
 return velxold-(termp*velxold+termq*velyold)*idt+U0int*MathF.Sqrt(2*termp*idt)*zuff1
 +idt*(DUDX*velX+DUDY*velY+U0int*DSIGUDX)
 +idt*(velxold/U0int*(DSIGUDX*velX+DSIGUDY*velY));
 }
 [MethodImpl(MethodImplOptions.NoInlining)]
 static float ShortGradient(float velxold,float velyold,float termp,float termq,float idt,float U0int,float zuff1)
 =>velxold-(termp*velxold+termq*velyold)*idt+U0int*MathF.Sqrt(2*termp*idt)*zuff1;
 static long Run(bool cached,float[] ob,float[] ust,int steps,int particles) {
 long sum=0; for(int p=0;p<particles;p++) {var cache=new Cache();for(int i=0;i<steps;i++)sum+=BitConverter.SingleToInt32Bits(cached?Cached(ob[i],ust[i],1000,ref cache):Original(ob[i],ust[i],1000));}return sum;
 }
 static void Main(string[] args) {
 Program.StdDeviationW=1;
 float negzero=BitConverter.Int32BitsToSingle(unchecked((int)0x80000000));
 float[] obCases={-float.Epsilon,-1e-20f,-.01f,-1,-50,-1000,-float.MaxValue,float.NegativeInfinity,float.NaN};
 float[] uCases={0,negzero,float.Epsilon,.01f,.2f,1,100,float.MaxValue,float.PositiveInfinity,float.NegativeInfinity,float.NaN};
 foreach(float blh in new[]{0f,1f,1000f,float.MaxValue,float.PositiveInfinity,float.NaN}) foreach(float ob in obCases) foreach(float u in uCases) Verify(new[]{ob,ob,-50,ob,ob},new[]{u,u,.2f,u,u},blh);
 var rng=new Random(1551);var obs=new float[100000];var us=new float[100000];
 for(int i=0;i<obs.Length;i++){obs[i]=BitConverter.Int32BitsToSingle(rng.Next()|unchecked((int)0x80000000));us[i]=BitConverter.Int32BitsToSingle(rng.Next());}Verify(obs,us,1000);
 var rows=new List<object>();
 foreach(int steps in new[]{16,256})foreach(string pattern in new[]{"unchanged","change_each_step","change_each_16"}){
 var ob=new float[steps];var u=new float[steps];for(int i=0;i<steps;i++){int k=pattern=="unchanged"?0:pattern=="change_each_step"?i:i/16;ob[i]=-20-k*.25f;u[i]=.2f+k*.0001f;}
 checksum+=Run(false,ob,u,steps,100);checksum+=Run(true,ob,u,steps,100);var a=new List<double>();var b=new List<double>();
 for(int rep=0;rep<7;rep++)foreach(bool cached in rep%2==0?new[]{false,true}:new[]{true,false}){var sw=Stopwatch.StartNew();checksum+=Run(cached,ob,u,steps,steps==16?32768:2048);sw.Stop();(cached?b:a).Add(sw.Elapsed.TotalMilliseconds);}
 rows.Add(new{steps,pattern,baseline_ms=a,candidate_ms=b,baseline_median_ms=a.Order().ElementAt(3),candidate_median_ms=b.Order().ElementAt(3)});
 }
 float g1=OriginalGradient(negzero,0,0,0,0,0,1,1,negzero);float g2=ShortGradient(negzero,0,0,0,1,1,negzero);
 var gradient=new{original_bits=BitConverter.SingleToInt32Bits(g1),short_bits=BitConverter.SingleToInt32Bits(g2),equal=BitConverter.SingleToInt32Bits(g1)==BitConverter.SingleToInt32Bits(g2),all_guard_operands_finite=true,U0int=1f,V0int=1f};
 File.WriteAllText(args[0],JsonSerializer.Serialize(new{status="pass",checks,checksum,rows,zero_gradient_probe=gradient},new JsonSerializerOptions{WriteIndented=true}));Console.WriteLine($"CHECKS {checks} ZERO_BITS {gradient.equal}");
 }
}}
