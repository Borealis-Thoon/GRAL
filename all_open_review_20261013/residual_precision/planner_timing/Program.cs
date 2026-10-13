using System; using System.Collections.Generic; using System.Threading; using System.Threading.Tasks; using System.Text.Json; using System.Diagnostics;
class Program { public static CancellationToken CancelToken=CancellationToken.None;public static float TAUS=1,TPS=2000000,DXK=1,DYK=1,GridVolume=1,TransConcThreshold=1;public static float[] DZK_Trans={0,1};public static int NII=256,NJJ=256,NKK_Transient=1;public static List<int> SourceGroups=new();public static ParallelOptions pOptions=new();public static float[][][][] Conz4d; }
class ParticleManagement {public static double ParticleMassActive=1;}
class Pbefore {
        private static double residualSplitK = 10;

        private static int ResidualSplitCount(double masse)
        {
            double split = Math.Floor(Math.Floor(masse / ParticleManagement.ParticleMassActive) / residualSplitK) + 1;
            return (int)Math.Min(100000, split > 1 ? split : 1);
        }

        // Six adjustments limit work toward the fresh-particle budget; this is not a hard cap.
        public static void PlanResidual()
        {
            if (Program.CancelToken.IsCancellationRequested) return;
            residualSplitK = 10;
            double budget = Program.TAUS * Program.TPS;
            if (budget <= 0 || ParticleManagement.ParticleMassActive <= 0)
            {
                return;
            }
            for (int it = 0; it < 6; it++)
            {
                long total = 0;
                System.Threading.Tasks.Parallel.For(1, Program.NII + 1, Program.pOptions, i =>
                {
                    if (Program.CancelToken.IsCancellationRequested) return;
                    long local = 0;
                    for (int j = 1; j <= Program.NJJ; j++)
                    {
                        for (int k = 1; k <= Program.NKK_Transient; k++)
                        {
                            double volume = Program.DXK * Program.DYK * Program.DZK_Trans[k] / Program.GridVolume;
                            float[] concentrations = Program.Conz4d[i][j][k];
                            for (int group = 0; group < Program.SourceGroups.Count; group++)
                            {
                                if (concentrations[group] >= Program.TransConcThreshold)
                                {
                                    local += ResidualSplitCount(concentrations[group] * volume / Program.TAUS);
                                }
                            }
                        }
                    }
                    Interlocked.Add(ref total, local);
                });
                if (Program.CancelToken.IsCancellationRequested) return;
                if (total <= budget) break;
                residualSplitK *= Math.Max(1.05, total / budget);
            }
        }


}
class Pafter {
        private static double residualSplitK = 10;

        private static int ResidualSplitCount(double masse)
        {
            double split = Math.Floor(Math.Floor(masse / ParticleManagement.ParticleMassActive) / residualSplitK) + 1;
            return (int)Math.Min(100000, split > 1 ? split : 1);
        }

        // Six adjustments limit work toward the fresh-particle budget; this is not a hard cap.
        public static void PlanResidual()
        {
            if (Program.CancelToken.IsCancellationRequested) return;
            residualSplitK = 10;
            double budget = Program.TAUS * Program.TPS;
            if (budget <= 0 || ParticleManagement.ParticleMassActive <= 0)
            {
                return;
            }
            for (int it = 0; it < 6; it++)
            {
                long total = 0, entries = 0;
                System.Threading.Tasks.Parallel.For(1, Program.NII + 1, Program.pOptions, i =>
                {
                    if (Program.CancelToken.IsCancellationRequested) return;
                    long local = 0, localEntries = 0;
                    for (int j = 1; j <= Program.NJJ; j++)
                    {
                        for (int k = 1; k <= Program.NKK_Transient; k++)
                        {
                            double volume = Program.DXK * Program.DYK * Program.DZK_Trans[k] / Program.GridVolume;
                            float[] concentrations = Program.Conz4d[i][j][k];
                            for (int group = 0; group < Program.SourceGroups.Count; group++)
                            {
                                if (concentrations[group] >= Program.TransConcThreshold)
                                {
                                    local += ResidualSplitCount(concentrations[group] * volume / Program.TAUS);
                                    localEntries++;
                                }
                            }
                        }
                    }
                    Interlocked.Add(ref total, local);
                    Interlocked.Add(ref entries, localEntries);
                });
                if (Program.CancelToken.IsCancellationRequested) return;
                if (total <= budget || total == entries) break;
                residualSplitK *= Math.Max(1.05, total / budget);
            }
        }


}
class Entry {static double Measure(Action a){var sw=Stopwatch.StartNew();for(int z=0;z<5;z++)a();return sw.Elapsed.TotalMilliseconds/5;}
static void Main(string[] args){for(int g=0;g<16;g++)Program.SourceGroups.Add(g);Program.Conz4d=new float[257][][][];for(int i=0;i<257;i++){Program.Conz4d[i]=new float[257][][];for(int j=0;j<257;j++){Program.Conz4d[i][j]=new float[2][];Program.Conz4d[i][j][1]=new float[16];Array.Fill(Program.Conz4d[i][j][1],1f);}}
var rows=new List<object>();foreach(int workers in new[]{1,4,24})foreach(string kind in new[]{"one_scan","at_floor"}){Program.pOptions.MaxDegreeOfParallelism=workers;Program.TPS=kind=="one_scan"?2000000:1000;for(int k=0;k<100;k++){Pbefore.PlanResidual();Pafter.PlanResidual();}for(int repeat=0;repeat<7;repeat++){double a,b;if(repeat%2==0){a=Measure(Pbefore.PlanResidual);b=Measure(Pafter.PlanResidual);}else{b=Measure(Pafter.PlanResidual);a=Measure(Pbefore.PlanResidual);}rows.Add(new{workers,kind,repeat,entries=1048576,budget=Program.TPS,before_ms=a,after_ms=b});}}
System.IO.File.WriteAllText(args[0],JsonSerializer.Serialize(rows));}}
