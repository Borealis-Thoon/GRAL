using System;
using System.IO;
using System.Reflection;
using System.Threading;

class Test
{
    static readonly Assembly Assembly = Assembly.Load("GRAL");
    static readonly Type Program = Assembly.GetType("GRAL_2001.Program", true);
    static readonly Type Driver = Assembly.GetType("GRAL_2001.GpuSituationDriver", true);
    static readonly Type Experimental = Assembly.GetType("GRAL_2001.GpuExperimental", true);
    const BindingFlags Flags = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
    static void Set(string name, object value) => Program.GetField(name, Flags).SetValue(null, value);
    static object Invoke(Type type, string name, params object[] args)
    {
        var method = type.GetMethod(name, Flags);
        if (method == null) throw new Exception("Missing method " + name);
        try { return method.Invoke(null, args); }
        catch (TargetInvocationException ex) { throw ex.InnerException; }
    }
    static void Check(bool value, string message) { if (!value) throw new Exception(message); }
    static void Throws<T>(Action action) where T : Exception
    { try { action(); } catch (T) { return; } throw new Exception("Expected " + typeof(T).Name); }
    static void Reset()
    {
        Set("ISTATIONAER", 0); Set("Topo", 1); Set("IStatistics", 4); Set("UseFixedRndSeedVal", true);
        Set("PS_Count", 0); Set("TS_Count", 0); Set("LS_Count", 1); Set("AS_Count", 1);
        Set("LS_Mode", new byte[2]); Set("AS_Mode", new byte[2]);
        Set("SourceType", new byte[] {0, 2, 3}); Set("ParticleMode", new byte[3]);
        Set("CancelToken", new CancellationTokenSource());
    }
    static bool Can(int first=1, int count=2) => (bool)Invoke(Experimental,"CanRun",first,count);
    static int Main(string[] args) { try { Run(args); return 0; } catch (Exception ex) { Console.Error.WriteLine("FAIL " + ex.Message); return 1; } }
    static void Run(string[] args)
    {
        Reset();
        Check(Can(), "Mixed line and area sources must run on GPU");
        Set("LS_Mode", new byte[]{0,1}); Check(!Can(1,0), "Line deposition must fall back with zero fresh particles");
        Reset(); Set("AS_Mode", new byte[]{0,1}); Check(!Can(1,0), "Area deposition must fall back with zero fresh particles");
        Reset(); Set("PS_Count",1); Set("SourceType", null); Check(!Can(), "Point sources must fall back before array access");
        Reset(); Set("TS_Count",1); Check(!Can(), "Portal sources must fall back");
        Reset(); Set("ISTATIONAER",1); Set("SourceType",null); Check(!Can(), "Steady state must fall back before array access");
        Reset(); Set("BuildingsExist",true); Check(!Can(), "Buildings must fall back"); Set("BuildingsExist",false);
        Reset(); Set("SourceType",new byte[]{0,0,3}); Check(!Can(), "Point particles must fall back");
        Reset(); Set("ParticleMode",new byte[]{0,1,0}); Check(!Can(), "Deposition particles must fall back");
        Reset(); Throws<InvalidOperationException>(()=>Can(0,1));
        Reset(); Set("LS_Mode",new byte[1]); Throws<InvalidOperationException>(()=>Can());
        Reset(); Set("ParticleMode",new byte[1]); Throws<InvalidOperationException>(()=>Can());
        Reset(); var token = new CancellationTokenSource(); token.Cancel(); Set("CancelToken",token); Throws<OperationCanceledException>(()=>Can());
        Reset(); Invoke(Driver,"Guard",1,2);
        var source=File.ReadAllText(args[0]);
        Check(source.Contains("GpuExperimental.Enabled && GpuExperimental.CanRun(1, NTEILMAX)"), "Enabled must short circuit selection");
        Check(source.Contains("if (!useGpu) { ParallelParticleDriver(1, NTEILMAX + 1); }"), "CPU fresh path must follow selection");
        Console.WriteLine("PASS dispatch tests");
    }
}
