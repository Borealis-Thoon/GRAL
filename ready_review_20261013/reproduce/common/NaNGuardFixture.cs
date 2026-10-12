using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

static class ExitProbeProgram
{
    public static Func<double,double,float,double,float,bool> Check;
    public static bool ReceptorsAvailable = true;
    public static double[][] ReceptorConc;
    public static double[][] ReceptorParticleMaxConc;
    public static bool ParticleStateIsFinite(double x,double y,float z,double mass,float dt) => Check(x,y,z,mass,dt);
    public static void Reset() { ReceptorConc = Make(); ReceptorParticleMaxConc = Make(); }
    public static double[][] Make() => Enumerable.Range(0,3).Select(_ => new double[2]).ToArray();
}
static class WetProbeProgram
{
    public static bool WetDeposition = true;
    public static double WetDepoRW;
    public static bool ForceExit = false;
    public static bool ParticleStateIsFinite(double x,double y,float z,double mass,float dt) => ExitProbeProgram.Check(x,y,z,mass,dt);
}
class NaNGuardFixture
{
    const BindingFlags F = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
    static int checks;
    static List<object> records = new();
    static void Assert(bool ok,string message) { if (!ok) throw new Exception(message); checks++; }
    static void Set(Type p,string name,object value)
    {
        var f=p.GetField(name,F);
        f.SetValue(null,f.FieldType.IsInstanceOfType(value) ? value : Convert.ChangeType(value,f.FieldType));
    }
    static T Get<T>(Type p,string name) => (T)p.GetField(name,F).GetValue(null);
    static void Setup(Type p)
    {
        Set(p,"DXK",20); Set(p,"DYK",20); Set(p,"GridVolume",1); Set(p,"TAUS",30);
        Set(p,"GralDx",20); Set(p,"GralDy",20); Set(p,"GralDz",2); Set(p,"NS",1);
        Set(p,"DDX",new float[]{0,20}); Set(p,"DDY",new float[]{0,20});
        Set(p,"Topo",0); Set(p,"LogLevel",0); Set(p,"ISTATIONAER",1); Set(p,"UseFixedRndSeedVal",false);
        Set(p,"ReceptorsAvailable",true); Set(p,"ReceptorNumber",2);
        Set(p,"ReceptorConc",ExitProbeProgram.Make()); Set(p,"ReceptorParticleMaxConc",ExitProbeProgram.Make());
        Set(p,"Xcoord",new double[]{0,25}); Set(p,"YCoord",new double[]{0,25}); Set(p,"ZCoord",new float[]{0,2});
        Set(p,"ParticleMass",new double[]{0,1}); Set(p,"ParticleSG",new byte[]{0,1});
        Set(p,"ParticleSource",new int[]{0,1}); Set(p,"SourceType",new byte[]{0,3});
        Set(p,"ParticleMode",new byte[]{0,0}); Set(p,"ParticleVsed",new float[2]); Set(p,"ParticleVdep",new float[2]);
        Set(p,"EmissionTimeseriesExist",false); Set(p,"IWET",1); Set(p,"DispTimeSum",30);
        Set(p,"EmissionPerSG",new double[]{17,19});
        var groups=Get<List<int>>(p,"SourceGroups"); groups.Clear(); groups.Add(1); groups.Add(2);
        Set(p,"AHK",Enumerable.Range(0,5).Select(_ => new float[5]).ToArray());
        Set(p,"NKK_Transient",8); Set(p,"HoKartTrans",Enumerable.Range(0,9).Select(x => x*10f).ToArray());
        Set(p,"DZK_Trans",Enumerable.Repeat(10f,9).ToArray());
        Set(p,"Conz5d",Enumerable.Range(0,5).Select(_=>Enumerable.Range(0,5).Select(_=>Enumerable.Range(0,9).Select(_=>new float[]{3,17}).ToArray()).ToArray()).ToArray());
    }
    static string Snapshot(Type p) => string.Join(",",Get<float[][][][]>(p,"Conz5d").SelectMany(x=>x.SelectMany(y=>y.SelectMany(z=>z))).Select(BitConverter.SingleToInt32Bits));
    static bool StorageNonFinite(Type p) => Get<float[][][][]>(p,"Conz5d").SelectMany(x=>x.SelectMany(y=>y.SelectMany(z=>z))).Any(x=>!float.IsFinite(x));
    static void InvokeStorage(Type p,Type methodType,string method,double x,double y,float z,float surface,double mass,double area,int reflection=0)
    { methodType.GetMethod(method,F).Invoke(null,new object[]{reflection,z,surface,mass,area,.1f,x,y,0}); }
    static void Main(string[] args)
    {
        var baseline = new AssemblyLoadContext("baseline",false).LoadFromAssemblyPath(Path.GetFullPath(args[0]));
        var state = new AssemblyLoadContext("state",false).LoadFromAssemblyPath(Path.GetFullPath(args[1]));
        var storage = new AssemblyLoadContext("storage",false).LoadFromAssemblyPath(Path.GetFullPath(args[2]));
        Type p=state.GetType("GRAL_2001.Program"), bp=baseline.GetType("GRAL_2001.Program"), sp=storage.GetType("GRAL_2001.Program");
        Type st=storage.GetType("GRAL_2001.TransientConcentration"), bt=baseline.GetType("GRAL_2001.TransientConcentration");
        var finite=p.GetMethod("ParticleStateIsFinite",F).CreateDelegate<Func<double,double,float,double,float,bool>>();
        ExitProbeProgram.Check=finite;
        long StateCount()=>Get<long>(p,"NonFiniteParticleCount");
        long WriteCount()=>Get<long>(st,"NonFiniteResidualWriteCount");
        void StateReset()=>Set(p,"NonFiniteParticleCount",0);
        void WriteReset()=>Set(st,"NonFiniteResidualWriteCount",0);
        int begin=checks;
        foreach(double value in new[]{0d,-0d,double.Epsilon,-double.Epsilon,double.MaxValue,-double.MaxValue,1d,-1d})
        {
            StateReset(); Assert(finite(value,value,1f,value,.1f),"Finite doubles removed"); Assert(StateCount()==0,"Finite counter");
        }
        foreach(float value in new[]{0f,-0f,float.Epsilon,-float.Epsilon,float.MaxValue,-float.MaxValue,1f,-1f})
        { StateReset(); Assert(finite(1,1,value,1,value),"Finite float removed"); Assert(StateCount()==0,"Finite float counter"); }
        foreach(double invalid in new[]{double.NaN,double.PositiveInfinity,double.NegativeInfinity})
            for(int field=0;field<5;field++)
            {
                double x=1,y=1,mass=1; float z=1,dt=.1f;
                if(field==0)x=invalid;if(field==1)y=invalid;if(field==2)z=(float)invalid;if(field==3)mass=invalid;if(field==4)dt=(float)invalid;
                StateReset(); Assert(!finite(x,y,z,mass,dt),"Invalid helper state survived"); Assert(StateCount()==1,"Helper count differs");
            }
        int helperChecks=checks-begin;
        begin=checks; int guardSites=0;
        foreach(var m in typeof(ExtractedParticleExit).GetMethods(F | BindingFlags.DeclaredOnly).Where(m=>m.Name.StartsWith("Guard_")))
        {
            guardSites++;
            foreach(double invalid in new[]{double.NaN,double.PositiveInfinity,double.NegativeInfinity})
                for(int field=0;field<5;field++)
                {
                    if(field==4 && !ExtractedParticleExit.HasTimeStepGuard(int.Parse(m.Name.Substring(6)))) continue;
                    double x=1,y=1,mass=1; float z=1,dt=.1f;
                    if(field==0)x=invalid;if(field==1)y=invalid;if(field==2)z=(float)invalid;if(field==3)mass=invalid;if(field==4)dt=(float)invalid;
                    StateReset(); ExitProbeProgram.Reset();
                    bool continued=(bool)m.Invoke(null,new object[]{x,y,z,mass,dt,1d});
                    Assert(!continued,"Production guard continued: "+m.Name);
                    Assert(StateCount()==1,"Guard exit counted twice");
                    Assert(ExitProbeProgram.ReceptorConc[1][0]==.25 && ExitProbeProgram.ReceptorConc[2][0]==1.5,"Prior receptor contribution lost");
                    Assert(ExitProbeProgram.ReceptorParticleMaxConc[1][0]==.25 && ExitProbeProgram.ReceptorParticleMaxConc[2][0]==1.5,"Prior receptor maximum lost");
                    Assert(ExitProbeProgram.ReceptorConc[1][1]==0,"Other source group contaminated");
                }
            StateReset();ExitProbeProgram.Reset();
            Assert((bool)m.Invoke(null,new object[]{0d,-0d,0f,0d,0f,0d}),"Finite zero branch removed");Assert(StateCount()==0,"Finite zero count");
        }
        int branchChecks=checks-begin;
        begin=checks; int wetCases=0;
        var wetRecords=new List<object>();
        foreach(string driver in new[]{"new","residual"})
        {
            var oldWet=typeof(ExtractedWetStep).GetMethod("warning_free_baseline_"+driver,F);
            var newWet=typeof(ExtractedWetStep).GetMethod("nan_guard_state_"+driver,F);
            foreach(double rw in new[]{0d,.02d,1d,double.NaN,double.PositiveInfinity,double.NegativeInfinity})
            {
                WetProbeProgram.WetDepoRW=rw; StateReset();
                object[] oldArgs={1d,.1f,0d,0d}; object[] newArgs={1d,.1f,0d,0d};
                bool oldReached=(bool)oldWet.Invoke(null,oldArgs), newReached=(bool)newWet.Invoke(null,newArgs);
                bool reject=double.IsNaN(rw)||double.IsNegativeInfinity(rw);
                Assert(newReached==(!reject && rw!=0),"Wet nonfinite write gate");
                Assert(StateCount()==(reject?1:0),"Wet state count");
                if(!reject)Assert(BitConverter.DoubleToInt64Bits((double)oldArgs[3])==BitConverter.DoubleToInt64Bits((double)newArgs[3]),"Finite wet arithmetic changed");
                wetRecords.Add(new{driver,coefficient=double.IsNaN(rw)?"NaN":double.IsPositiveInfinity(rw)?"positive_inf":double.IsNegativeInfinity(rw)?"negative_inf":rw.ToString(System.Globalization.CultureInfo.InvariantCulture),baseline_reaches_write=oldReached,baseline_remaining_mass_finite=double.IsFinite((double)oldArgs[3]),candidate_reaches_write=newReached,candidate_rejected_states=StateCount()});wetCases++;
            }
            WetProbeProgram.WetDepoRW=0;StateReset();
            object[] decayArgs={1d,0f,double.PositiveInfinity,0d};
            Assert(!(bool)newWet.Invoke(null,decayArgs),"NaN decay reached output");Assert(StateCount()==1,"NaN decay state not counted");wetCases++;
        }
        int wetChecks=checks-begin;
        begin=checks; int actualDriverCases=0;
        foreach(double invalid in new[]{double.NaN,double.PositiveInfinity,double.NegativeInfinity})
            for(int field=0;field<4;field++)
            {
                Setup(p); StateReset();
                if(field==0)Get<double[]>(p,"Xcoord")[1]=invalid;
                if(field==1)Get<double[]>(p,"YCoord")[1]=invalid;
                if(field==2)Get<float[]>(p,"ZCoord")[1]=(float)invalid;
                if(field==3)Get<double[]>(p,"ParticleMass")[1]=invalid;
                state.GetType("GRAL_2001.Zeitschleife").GetMethod("Calculate",F).Invoke(null,new object[]{1}); actualDriverCases++;
                Assert(StateCount()==1,"Actual driver initial removal count");
                Assert(Get<double[][]>(p,"ReceptorConc").All(x=>x.All(double.IsFinite)),"Initial driver receptor polluted");
                Assert(Get<double[]>(p,"EmissionPerSG").SequenceEqual(new double[]{17,19}),"Invalid initial mass reached emission sum");
            }
        foreach(double invalid in new[]{double.NaN,double.PositiveInfinity})
        {
            Setup(p);StateReset();Set(p,"ISTATIONAER",0);Set(p,"EmissionTimeseriesExist",true);
            Set(p,"EmFacTimeSeries",new float[,]{{(float)invalid,1},{1,1}});
            state.GetType("GRAL_2001.Zeitschleife").GetMethod("Calculate",F).Invoke(null,new object[]{1});actualDriverCases++;
            Assert(StateCount()==1,"Invalid emission modulation not counted");Assert(Get<double[]>(p,"EmissionPerSG").SequenceEqual(new double[]{17,19}),"Modulation polluted shared sum");
        }
        foreach(float invalid in new[]{float.NaN,float.PositiveInfinity,float.NegativeInfinity})
        {
            Setup(p);StateReset();Get<float[]>(p,"HoKartTrans")[1]=invalid;
            state.GetType("GRAL_2001.ZeitschleifeNonSteadyState").GetMethod("ParticleDriver",F).Invoke(null,new object[]{1,1,1,0,1f,0});actualDriverCases++;
            Assert(StateCount()==1,"Actual residual invalid height count");Assert(Get<double[][]>(p,"ReceptorConc").All(x=>x.All(double.IsFinite)),"Residual initial receptor polluted");
            Setup(p);StateReset();
            state.GetType("GRAL_2001.ZeitschleifeNonSteadyState").GetMethod("Calculate",F).Invoke(null,new object[]{1,1,1,0,invalid});actualDriverCases++;
            Assert(StateCount()==1,"Residual splitter invalid mass not counted");
        }
        int driverChecks=checks-begin;
        begin=checks; int normalStoreCases=0;
        foreach(string method in new[]{"Conz5dZeitschleife","Conz5dZeitschleifeTransient"})
            foreach(double mass in new[]{0d,-0d,double.Epsilon,1e-30,1d,1e10,-1d})
                foreach(float height in new[]{0f,10f,MathF.BitIncrement(10),79f})
                {
                    Setup(bp);Setup(sp);WriteReset();
                    InvokeStorage(bp,bt,method,25,25,height,0,mass,400);
                    InvokeStorage(sp,st,method,25,25,height,0,mass,400);
                    Assert(Snapshot(bp)==Snapshot(sp),"Finite write differs");Assert(WriteCount()==0,"Finite write rejected");normalStoreCases++;
                }
        int normalStorageChecks=checks-begin;
        begin=checks;int faultyStoreCases=0,baselinePolluted=0,baselineExceptions=0;
        foreach(string method in new[]{"Conz5dZeitschleife","Conz5dZeitschleifeTransient"})
        {
            var faults=new List<(string label,double x,double y,float z,float surface,double mass,double area,float existing)>();
            foreach(double bad in new[]{double.NaN,double.PositiveInfinity,double.NegativeInfinity})
            { string tag=double.IsNaN(bad)?"NaN":bad>0?"positive_inf":"negative_inf";
                faults.Add(("x_"+tag,bad,25,2,0,1,400,3));faults.Add(("y_"+tag,25,bad,2,0,1,400,3));
                faults.Add(("z_"+tag,25,25,(float)bad,0,1,400,3));faults.Add(("mass_"+tag,25,25,2,0,bad,400,3));
            }
            faults.Add(("relative_height_overflow",25,25,float.MaxValue,-float.MaxValue,1,400,3));
            faults.Add(("float_increment_overflow",25,25,2,0,double.MaxValue,400,3));
            faults.Add(("zero_storage_volume",25,25,2,0,1,0,3));
            double additiveMass=(double)float.MaxValue*400*10/(30*(method=="Conz5dZeitschleife"?1:1));
            faults.Add(("finite_sum_overflow",25,25,2,0,additiveMass,400,float.MaxValue));
            foreach(var c in faults)
            {
                Setup(bp);Setup(sp);WriteReset();
                Get<float[][][][]>(bp,"Conz5d")[2][2][1][0]=c.existing;Get<float[][][][]>(sp,"Conz5d")[2][2][1][0]=c.existing;
                string before=Snapshot(sp),baselineBefore=Snapshot(bp),error=null;
                try{InvokeStorage(bp,bt,method,c.x,c.y,c.z,c.surface,c.mass,c.area);}catch(TargetInvocationException e){error=e.InnerException.GetType().Name;baselineExceptions++;}
                bool polluted=StorageNonFinite(bp);if(polluted)baselinePolluted++;
                InvokeStorage(sp,st,method,c.x,c.y,c.z,c.surface,c.mass,c.area);
                Assert(Snapshot(sp)==before,"Rejected write changed cell: "+c.label);Assert(WriteCount()==1,"Rejected storage count");Assert(!StorageNonFinite(sp),"Candidate storage nonfinite");
                records.Add(new{method,fault=c.label,baseline_nonfinite=polluted,baseline_exception=error,baseline_grid_changed=Snapshot(bp)!=baselineBefore,candidate_cell_unchanged=true,candidate_rejected_writes=WriteCount()});faultyStoreCases++;
            }
            Setup(sp);WriteReset();InvokeStorage(sp,st,method,double.NaN,25,2,0,double.NaN,400,1);
            Assert(WriteCount()==0,"Reflected write counted");
        }
        int faultyStorageChecks=checks-begin;
        begin=checks;
        foreach(int workers in new[]{1,2})
        {
            StateReset();Parallel.For(0,240,new ParallelOptions{MaxDegreeOfParallelism=workers},i=>{ bool ok=finite(1,1,1,i%2==0?double.NaN:1,.1f);if(ok!=(i%2!=0))throw new Exception("Parallel state branch"); });
            Assert(StateCount()==120,"Atomic state counter lost increments");
            foreach(string method in new[]{"Conz5dZeitschleife","Conz5dZeitschleifeTransient"})
            {
                Setup(bp);Setup(sp);WriteReset();
                for(int i=0;i<120;i++)InvokeStorage(bp,bt,method,25,25,2,0,2,400);
                Parallel.For(0,240,new ParallelOptions{MaxDegreeOfParallelism=workers},i=>InvokeStorage(sp,st,method,25,25,2,0,i%2==0?double.NaN:2,400));
                Assert(WriteCount()==120,"Atomic storage counter lost increments");Assert(Snapshot(sp)==Snapshot(bp),"Valid concurrent write polluted");
            }
        }
        Set(p,"NonFiniteParticleCount",(long)int.MaxValue);
        Assert(!finite(1,1,1,double.NaN,.1f),"Boundary counter state accepted");Assert(StateCount()==2147483648L,"State counter Int32 boundary overflow");
        Setup(sp);Set(st,"NonFiniteResidualWriteCount",(long)int.MaxValue);
        InvokeStorage(sp,st,"Conz5dZeitschleife",25,25,2,0,double.NaN,400);
        Assert(WriteCount()==2147483648L,"Residual write counter Int32 boundary overflow");
        int parallelChecks=checks-begin;
        begin=checks;int reportCases=0;
        foreach(bool residual in new[]{false,true})
            foreach(long count in new[]{0L,1L,2147483648L,long.MaxValue})
            {
                StateReportProbe.NonFiniteParticleCount=count;ReportFixtureStorageCounter.NonFiniteResidualWriteCount=count;
                ReportFixtureLog.Lines.Clear();var capture=new StringWriter();var previous=Console.Out;
                Console.SetOut(capture);try { if(residual)StorageReportProbe.Run();else StateReportProbe.Run(); }finally { Console.SetOut(previous); }
                long remainder=residual?ReportFixtureStorageCounter.NonFiniteResidualWriteCount:StateReportProbe.NonFiniteParticleCount;
                Assert(remainder==0,"Report did not atomically reset");
                Assert(ReportFixtureLog.Lines.Count==(count==0?0:1),"Zero report log or missing positive count");
                Assert((capture.ToString().Length==0)==(count==0),"Zero report console or missing positive count");
                if(count>0)Assert(ReportFixtureLog.Lines[0].Contains(count.ToString()) && ReportFixtureLog.Lines[0].Contains("17"),"Report count/situation missing");
                ReportFixtureLog.Lines.Clear();capture=new StringWriter();Console.SetOut(capture);
                try { if(residual)StorageReportProbe.Run();else StateReportProbe.Run(); }finally { Console.SetOut(previous); }
                Assert(ReportFixtureLog.Lines.Count==0 && capture.ToString().Length==0,"Count reported twice");reportCases++;
            }
        int reportChecks=checks-begin;
        begin=checks;int expiryFaultCases=0,expiryNormalPairs=0;
        ExpiryStorageFixture.Save=(r,z,h,m,a,dt,x,y,sg)=>InvokeStorage(bp,bt,"Conz5dZeitschleife",x,y,z,h,m,a,r);
        var expiryRecords=new List<object>();
        foreach(int sourceType in new[]{0,1,2,3})
        {
            foreach(float invalidZ in new[]{float.NaN,float.PositiveInfinity,float.NegativeInfinity})
            {
                Setup(bp);StateReset();ExpiryStorageFixture.Calls=0;
                ExtractedTransientExpiry.warning_free_baseline(sourceType,invalidZ,0,.1f,true);
                int baselineCalls=ExpiryStorageFixture.Calls;
                Setup(bp);StateReset();ExpiryStorageFixture.Calls=0;string before=Snapshot(bp);
                Assert(!ExtractedTransientExpiry.nan_guard_state(sourceType,invalidZ,0,.1f,true),"Invalid expiry branch survived");
                Assert(ExpiryStorageFixture.Calls==0 && Snapshot(bp)==before,"State-only expiry reached unpatched storage");Assert(StateCount()==1,"Expiry state count");
                expiryRecords.Add(new{source_type=sourceType,case_name=float.IsNaN(invalidZ)?"NaN_z":invalidZ>0?"positive_inf_z":"negative_inf_z",baseline_storage_calls=baselineCalls,candidate_storage_calls=ExpiryStorageFixture.Calls});expiryFaultCases++;
            }
            Setup(bp);StateReset();ExpiryStorageFixture.Calls=0;
            Assert(!ExtractedTransientExpiry.nan_guard_state(sourceType,2,float.MaxValue,2,true),"Finite vertical overflow survived expiry");
            Assert(ExpiryStorageFixture.Calls==0 && StateCount()==1,"Finite overflow expiry gate");expiryFaultCases++;
            foreach(float z in new[]{0f,2f,10f,MathF.BitIncrement(10),float.Epsilon})
                foreach(float settling in new[]{0f,.01f})
                {
                    Setup(bp);StateReset();ExpiryStorageFixture.Calls=0;
                    ExtractedTransientExpiry.warning_free_baseline(sourceType,z,settling,.1f,true);
                    string baselineGrid=Snapshot(bp);int baselineCalls=ExpiryStorageFixture.Calls;
                    Setup(bp);StateReset();ExpiryStorageFixture.Calls=0;
                    ExtractedTransientExpiry.nan_guard_state(sourceType,z,settling,.1f,true);
                    Assert(Snapshot(bp)==baselineGrid,"Finite expiry float grid differs");Assert(ExpiryStorageFixture.Calls==baselineCalls && baselineCalls==1,"Finite expiry storage count differs");Assert(StateCount()==0,"Finite expiry rejected");expiryNormalPairs++;
                }
        }
        int expiryChecks=checks-begin;
        begin=checks;
        float endpointNaN=ExtractedRngEndpoint.Normal(uint.MaxValue,uint.MaxValue,out float uniformNaN);
        Assert(uniformNaN==0 && float.IsNaN(endpointNaN),"Unchanged zero uniform endpoint differs");
        float endpointInf=ExtractedRngEndpoint.Normal(uint.MaxValue,12345,out float uniformInf);
        Assert(uniformInf==0 && float.IsInfinity(endpointInf),"Unchanged infinity endpoint differs");
        StateReset();Assert(!finite(1,1,endpointNaN,1,.1f),"Endpoint-generated NaN not rejected");Assert(StateCount()==1,"Endpoint rejection count");
        int rngEndpointChecks=checks-begin;
        File.WriteAllText(args[3],JsonSerializer.Serialize(new{status="pass",checks_passed=checks,helper_checks=helperChecks,production_guard_sites=guardSites,production_branch_checks=branchChecks,actual_driver_cases=actualDriverCases,actual_driver_checks=driverChecks,wet_arithmetic_cases=wetCases,wet_arithmetic_checks=wetChecks,wet_arithmetic_records=wetRecords,normal_storage_cases=normalStoreCases,normal_storage_checks=normalStorageChecks,faulty_storage_cases=faultyStoreCases,faulty_storage_checks=faultyStorageChecks,baseline_fault_cases_with_nonfinite_storage=baselinePolluted,baseline_fault_cases_with_exceptions=baselineExceptions,parallel_workers=new[]{1,2},parallel_checks=parallelChecks,report_cases=reportCases,report_checks=reportChecks,expiry_fault_cases=expiryFaultCases,expiry_normal_pairs=expiryNormalPairs,expiry_checks=expiryChecks,expiry_records=expiryRecords,rng_endpoint_checks=rngEndpointChecks,fault_records=records,scope="Actual baseline/candidate DLL helper, initial particle drivers and both storage methods; extracted production guards and receptor-exit code for mid-step control flow. No full Main fault injection in this fixture."},new JsonSerializerOptions{WriteIndented=true}));
        Console.WriteLine("[PASS] "+checks+" checks; "+actualDriverCases+" actual driver cases; "+faultyStoreCases+" faulty storage cases");
    }
}
