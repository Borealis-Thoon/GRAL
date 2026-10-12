using System;
using System.Collections.Generic;
using System.Threading;
using ProgramWriters = ReportFixtureLog;
using TransientConcentration = ReportFixtureStorageCounter;
static class ReportFixtureLog { public static List<string> Lines=new(); public static void LogfileGralCoreWrite(string s) => Lines.Add(s); }
static class ReportFixtureStorageCounter { public static long NonFiniteResidualWriteCount; }
static class StateReportProbe
{
    public static long NonFiniteParticleCount;
    public static int IWET = 17;
    public static void Run()
    {
        string Info;
                    long nonFiniteParticles = Interlocked.Exchange(ref NonFiniteParticleCount, 0);
                    if (nonFiniteParticles > 0)
                    {
                        Info = $"Rejected {nonFiniteParticles} non-finite particle states in weather situation {IWET}.";
                        Console.WriteLine(Info);
                        ProgramWriters.LogfileGralCoreWrite(Info);
                    }

    }
}
static class StorageReportProbe
{
    public static int IWET = 17;
    public static void Run()
    {
        string Info;
                    long nonFiniteResidualWrites = Interlocked.Exchange(ref TransientConcentration.NonFiniteResidualWriteCount, 0);
                    if (nonFiniteResidualWrites > 0)
                    {
                        Info = $"Skipped {nonFiniteResidualWrites} non-finite residual writes in weather situation {IWET}.";
                        Console.WriteLine(Info);
                        ProgramWriters.LogfileGralCoreWrite(Info);
                    }

    }
}
