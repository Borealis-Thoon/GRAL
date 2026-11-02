using System;
using System.Reflection;
using System.Threading;

class NewModeDispatch
{
    static readonly Assembly Model = Assembly.Load("GRAL");
    static readonly Type Program = Model.GetType("GRAL_2001.Program", true);
    static readonly Type Driver = Model.GetType("GRAL_2001.GpuSituationDriver", true);
    const BindingFlags Flags = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
    static void Set(string name, object value) => Program.GetField(name, Flags).SetValue(null, value);
    static void Reset()
    {
        Set("ISTATIONAER", 0); Set("Topo", 1); Set("IStatistics", 4); Set("UseFixedRndSeedVal", true);
        foreach (string flag in new[] { "BuildingsExist", "WetDeposition", "DepositionExist", "Odour", "WriteVerticalConcentration", "TunnelEntr", "TunnelOppLane" }) Set(flag, false);
        Set("AdaptiveRoughnessMax", 0f); Set("LogLevel", 0); Set("NS", 1); Set("ReceptorNumber", 0);
        Set("ReceptorNearbyBuilding", new bool[1]); Array.Clear((double[])Program.GetField("DecayRate", Flags).GetValue(null));
        Set("PS_Count", 0); Set("TS_Count", 0); Set("LS_Count", 0); Set("AS_Count", 0); Set("IWET", 1);
        Set("PS_Mode", new byte[2]); Set("TS_Mode", new byte[2]);
        foreach (string name in new[] { "PS_TimeSeriesTemperature", "PS_TimeSeriesVelocity", "TS_TimeSeriesTemperature", "TS_TimeSeriesVelocity" }) Set(name, new int[] { -1, -1 });
        Set("SourceType", new byte[] { 0, 3, 3 }); Set("ParticleSource", new int[] { 0, 1, 1 }); Set("ParticleMode", new byte[3]);
        foreach (string name in new[] { "PS_D", "PS_HorExitDir", "PS_HorExitVel", "PS_T", "PS_V", "TS_Area", "TS_Height", "TS_Width", "TS_T", "TS_V", "TS_X1", "TS_X2", "TS_Y1", "TS_Y2" })
        {
            Type type = Program.GetField(name, Flags).FieldType.GetElementType();
            Array array = Array.CreateInstance(type, 2);
            array.SetValue(Convert.ChangeType(1, type), 1);
            Set(name, array);
        }
        Set("CancelToken", new CancellationTokenSource());
    }
    static int Main()
    {
        int failed = 0;
        void Test(string name, Action setup)
        {
            Reset(); setup();
            string reason = (string)Driver.GetMethod("GetUnsupportedReason", Flags).Invoke(null, new object[] { 1, 2 });
            if (reason != null) { Console.WriteLine("FAIL " + name + ": " + reason); failed++; }
            else Console.WriteLine("PASS " + name);
        }
        Test("steady_area", () => { Set("ISTATIONAER", 1); Set("AS_Count", 1); Set("AS_Mode", new byte[2]); });
        Test("steady_line", () => { Set("ISTATIONAER", 1); Set("LS_Count", 1); Set("LS_Mode", new byte[2]); Set("SourceType", new byte[] { 0, 2, 2 }); });
        Test("transient_point", () => { Set("PS_Count", 1); Set("SourceType", new byte[] { 0, 0, 0 }); });
        Test("transient_portal", () => { Set("TS_Count", 1); Set("SourceType", new byte[] { 0, 1, 1 }); });
        Test("mixed_point_area", () => { Set("PS_Count", 1); Set("AS_Count", 1); Set("AS_Mode", new byte[2]); Set("SourceType", new byte[] { 0, 0, 3 }); });
        return failed == 0 ? 0 : 1;
    }
}
