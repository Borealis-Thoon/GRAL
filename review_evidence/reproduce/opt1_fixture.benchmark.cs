using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Linq.Expressions;
using System.Reflection;
using System.Runtime;
using System.Security.Cryptography;
using System.Text.Json;

static class Opt1Bench
{
    static int sink;
    static double Median(IEnumerable<double> x){var a=x.Order().ToArray();return a[a.Length/2];}
    static Func<float[],int,int> LookupLoop(Engine engine,bool cached)
    {
        var heights=Expression.Parameter(typeof(float[]),"heights");var repeats=Expression.Parameter(typeof(int),"repeats");
        var i=Expression.Variable(typeof(int),"i");var k=Expression.Variable(typeof(int),"k");var sum=Expression.Variable(typeof(int),"sum");
        Type? cache=cached?engine.WindType.GetNestedType("WindSearch",BindingFlags.NonPublic):null;
        var state=cached?Expression.Variable(cache!,"state"):null;
        var done=Expression.Label("done");var innerDone=Expression.Label("innerDone");
        var height=Expression.ArrayIndex(heights,k);
        MethodInfo method=cached?engine.WindType.GetMethod("BinarySearch",BindingFlags.Static|BindingFlags.NonPublic,null,new[]{typeof(float),cache!.MakeByRefType()},null)!:engine.WindType.GetMethod("BinarySearch",BindingFlags.Static|BindingFlags.Public,null,new[]{typeof(float)},null)!;
        Expression lookup=cached?Expression.Call(method,height,state!):Expression.Call(method,height);
        var inner=Expression.Loop(Expression.IfThenElse(Expression.LessThan(k,Expression.ArrayLength(heights)),Expression.Block(Expression.AddAssign(sum,lookup),Expression.PostIncrementAssign(k)),Expression.Break(innerDone)),innerDone);
        var particle=new List<Expression>();if(cached)particle.Add(Expression.Assign(state!,Expression.New(cache!.GetConstructor(Type.EmptyTypes)!)));
        particle.Add(Expression.Assign(k,Expression.Constant(0)));particle.Add(inner);particle.Add(Expression.PostIncrementAssign(i));
        var outer=Expression.Loop(Expression.IfThenElse(Expression.LessThan(i,repeats),Expression.Block(particle),Expression.Break(done)),done);
        var vars=new List<ParameterExpression>{i,k,sum};if(cached)vars.Add(state!);
        return Expression.Lambda<Func<float[],int,int>>(Expression.Block(vars,Expression.Assign(i,Expression.Constant(0)),Expression.Assign(sum,Expression.Constant(0)),outer,sum),heights,repeats).Compile();
    }
    static Func<int,int> PrepareLoop(Engine engine)
    {
        Type cache=engine.WindType.GetNestedType("WindSearch",BindingFlags.NonPublic)!;
        var state=Expression.Variable(cache,"state");var i=Expression.Variable(typeof(int),"i");var sum=Expression.Variable(typeof(int),"sum");var repeats=Expression.Parameter(typeof(int),"repeats");var done=Expression.Label("done");
        var body=Expression.Block(Expression.Assign(state,Expression.New(cache.GetConstructor(Type.EmptyTypes)!)),Expression.AddAssign(sum,Expression.Field(state,"Count")),Expression.PostIncrementAssign(i));
        var loop=Expression.Loop(Expression.IfThenElse(Expression.LessThan(i,repeats),body,Expression.Break(done)),done);
        return Expression.Lambda<Func<int,int>>(Expression.Block(new[]{state,i,sum},Expression.Assign(i,Expression.Constant(0)),Expression.Assign(sum,Expression.Constant(0)),loop,sum),repeats).Compile();
    }
    static double Time(Func<int> run)
    {
        long t=Stopwatch.GetTimestamp();sink^=run();return Stopwatch.GetElapsedTime(t).TotalMilliseconds;
    }
    static int Repetitions(Func<int,int> run)
    {
        int r=32;while(r<(1<<20)&&Time(()=>run(r))<16)r*=2;return r;
    }
    static float[] Workload(int n,int length,string name)
    {
        int mid=Math.Max(1,n/2);float center=(mid-0.5F)*10F;
        return Enumerable.Range(0,length).Select(k=>name switch{
            "same_height"=>center,
            "same_layer"=>center+((k%9)-4)*0.5F,
            "large_jumps"=>((k*53)%(n+1))*10F+0.5F,
            _=>throw new ArgumentException(name)}).ToArray();
    }
    static void Main(string[] args)
    {
        if(args.Length!=4)throw new ArgumentException("baseline.dll stack.dll vertical.dll output.json");
        var before=new Engine(args[0]);var stack=new Engine(args[1]);var vertical=new Engine(args[2]);
        var plain=LookupLoop(before,false);var hinted=LookupLoop(vertical,true);var prepare=PrepareLoop(vertical);
        var rows=new List<object>();var prepares=new List<object>();var stackRows=new List<object>();
        foreach(int n in new[]{1,7,8,16,162})
        {
            float[] levels=Enumerable.Range(0,n+3).Select(k=>k*10F).ToArray();before.Profile((float[])levels.Clone(),n);vertical.Profile((float[])levels.Clone(),n);
            for(int w=0;w<100;w++)sink^=prepare(32);
            int prepCount=Repetitions(prepare);var prepMs=Enumerable.Range(0,7).Select(_=>Time(()=>prepare(prepCount))).ToArray();
            prepares.Add(new{nkk=n,repetitions=prepCount,median_ns_per_preparation=Median(prepMs)*1e6/prepCount,rounds_ms=prepMs});
            foreach(int length in new[]{8,64,256})foreach(string workload in new[]{"same_height","same_layer","large_jumps"})
            {
                float[] heights=Workload(n,length,workload);
                for(int w=0;w<100;w++){sink^=plain(heights,32);sink^=hinted(heights,32);}
                int repeats=Repetitions(r=>plain(heights,r));var oldMs=new List<double>();var newMs=new List<double>();
                for(int round=0;round<7;round++)
                {
                    if((round&1)==0){oldMs.Add(Time(()=>plain(heights,repeats)));newMs.Add(Time(()=>hinted(heights,repeats)));}
                    else{newMs.Add(Time(()=>hinted(heights,repeats)));oldMs.Add(Time(()=>plain(heights,repeats)));}
                }
                long count=(long)length*repeats;
                rows.Add(new{nkk=n,lookups_per_particle=length,workload,particle_repetitions=repeats,total_lookups=count,baseline_ns_per_lookup=Median(oldMs)*1e6/count,candidate_ns_per_lookup_including_per_particle_preparation=Median(newMs)*1e6/count,baseline_over_candidate=Median(oldMs)/Median(newMs),baseline_rounds_ms=oldMs,candidate_rounds_ms=newMs});
            }
        }
        foreach(int ns in new[]{1,9,512,513})
        {
            before.EarlyDriver(ns);stack.EarlyDriver(ns);
            for(int i=0;i<1024;i++){before.Driver(1);stack.Driver(1);}
            const int repetitions=4096;var oldTimes=new List<double>();var newTimes=new List<double>();var oldAlloc=new List<double>();var newAlloc=new List<double>();
            (double elapsed,double bytes) Measure(Action<int> driver)
            {
                long startBytes=GC.GetAllocatedBytesForCurrentThread();long start=Stopwatch.GetTimestamp();
                for(int p=0;p<repetitions;p++)driver(1);
                return(Stopwatch.GetElapsedTime(start).TotalMilliseconds,(GC.GetAllocatedBytesForCurrentThread()-startBytes)/(double)repetitions);
            }
            for(int round=0;round<7;round++)
            {
                (double elapsed,double bytes) a,b;
                if((round&1)==0){a=Measure(before.Driver);b=Measure(stack.Driver);}else{b=Measure(stack.Driver);a=Measure(before.Driver);}
                oldTimes.Add(a.elapsed);newTimes.Add(b.elapsed);oldAlloc.Add(a.bytes);newAlloc.Add(b.bytes);
            }
            stackRows.Add(new{ns,repetitions,baseline_bytes_per_entry=Median(oldAlloc),candidate_bytes_per_entry=Median(newAlloc),baseline_median_ns_per_entry=Median(oldTimes)*1e6/repetitions,candidate_median_ns_per_entry=Median(newTimes)*1e6/repetitions,baseline_rounds_ms=oldTimes,candidate_rounds_ms=newTimes});
        }
        var result=new{status="complete",rounds=7,runtime=Environment.Version.ToString(),os=Environment.OSVersion.VersionString,stopwatch_frequency=Stopwatch.Frequency,processor=Environment.GetEnvironmentVariable("PROCESSOR_IDENTIFIER"),server_gc=GCSettings.IsServerGC,dlls=new[]{before,stack,vertical}.Select(e=>new{path=e.Dll,sha256=Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(e.Dll)))}),vertical_lookup=rows,vertical_preparation=prepares,stack_entries=stackRows,scope="Actual compiled DLL methods. Vertical timing includes a fresh exact-height value-type cache preparation per particle and 8/64/256 lookups. Stack timing/allocation reaches the production slice declaration then removes an out-of-domain particle. Neither is full-model speedup. Dynamic-method loops and a single worker isolate lookup/declaration cost; no meteorology, geometry, tracking, I/O or parallel speedup is measured.",sink};
        File.WriteAllText(args[3],JsonSerializer.Serialize(result,new JsonSerializerOptions{WriteIndented=true}));Console.WriteLine(JsonSerializer.Serialize(new{result.status,vertical_cases=rows.Count,preparation_cases=prepares.Count,stack_cases=stackRows.Count}));
    }
}
