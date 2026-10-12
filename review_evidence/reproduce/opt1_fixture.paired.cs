using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Linq.Expressions;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;

static class Opt1PairedBench
{
    static int sink;
    static double Median(IEnumerable<double> values){var a=values.Order().ToArray();return a[a.Length/2];}
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
    static double Time(Func<int> run)
    {
        long t=Stopwatch.GetTimestamp();sink^=run();return Stopwatch.GetElapsedTime(t).TotalMilliseconds;
    }
    static int Repetitions(Func<int,int> run)
    {
        int repeats=32;while(repeats<(1<<20)&&Time(()=>run(repeats))<16)repeats*=2;return repeats;
    }
    static float[] Workload(int n,int length,string name)
    {
        int mid=Math.Max(1,n/2);float center=(mid-0.5F)*10F;
        return Enumerable.Range(0,length).Select(k=>name switch {
            "paired_same_layer"=>center+(((k/2)%9)-4)*0.5F,
            "paired_large_jumps"=>(((k/2)*53)%(n+1))*10F+0.5F,
            _=>throw new ArgumentException(name)
        }).ToArray();
    }
    static void Main(string[] args)
    {
        if(args.Length!=3)throw new ArgumentException("baseline.dll vertical.dll output.json");
        var before=new Engine(args[0]);var candidate=new Engine(args[1]);
        var plain=LookupLoop(before,false);var cached=LookupLoop(candidate,true);var rows=new List<object>();int oracleChecks=0;
        foreach(int n in new[]{1,39,162})
        {
            float[] levels=Enumerable.Range(0,n+3).Select(k=>k*10F).ToArray();before.Profile((float[])levels.Clone(),n);candidate.Profile((float[])levels.Clone(),n);
            foreach(int length in new[]{8,64,256})foreach(string name in new[]{"paired_same_layer","paired_large_jumps"})
            {
                float[] heights=Workload(n,length,name);
                for(int k=0;k<length;k+=2)if(heights[k]!=heights[k+1]||(k>0&&heights[k-1]==heights[k]))throw new InvalidOperationException("Expected exactly one repeated height per pair.");
                foreach(int repetitions in new[]{1,32})
                {
                    int oldSum=plain(heights,repetitions);int newSum=cached(heights,repetitions);oracleChecks++;
                    if(oldSum!=newSum)throw new InvalidOperationException($"Result mismatch NKK={n}, length={length}, workload={name}.");
                }
                for(int w=0;w<100;w++){sink^=plain(heights,32);sink^=cached(heights,32);}
                int repeats=Repetitions(r=>plain(heights,r));var oldMs=new List<double>();var newMs=new List<double>();
                for(int round=0;round<7;round++)
                {
                    if((round&1)==0){oldMs.Add(Time(()=>plain(heights,repeats)));newMs.Add(Time(()=>cached(heights,repeats)));}
                    else{newMs.Add(Time(()=>cached(heights,repeats)));oldMs.Add(Time(()=>plain(heights,repeats)));}
                }
                long lookups=(long)repeats*length;double ratio=Median(oldMs)/Median(newMs);
                rows.Add(new{nkk=n,lookups_per_particle=length,workload=name,synthetic_consecutive_repeat_fraction=0.5,particle_repetitions=repeats,total_lookups=lookups,baseline_ns_per_lookup=Median(oldMs)*1e6/lookups,candidate_ns_per_lookup_including_per_particle_preparation=Median(newMs)*1e6/lookups,baseline_over_candidate=ratio,candidate_runtime_percent_change=(1/ratio-1)*100,baseline_rounds_ms=oldMs,candidate_rounds_ms=newMs});
            }
        }
        var result=new{status="pass",conditions=rows.Count,oracle_checks=oracleChecks,paired_rounds=7,synthetic_consecutive_repeat_fraction=0.5,scope="Synthetic paired height sequences with exactly 50% consecutive repeats. NKK=39 matches the two synthetic terrain test grids. These sequences are not a replay of actual Main heights. Compiled production DLL searches with a fresh value-type cache per particle; preparation is included. This measures lookup cost, not full-model runtime.",runtime=Environment.Version.ToString(),stopwatch_frequency=Stopwatch.Frequency,dlls=new[]{before,candidate}.Select(e=>new{path=e.Dll,sha256=Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(e.Dll)))}),records=rows,sink};
        File.WriteAllText(args[2],JsonSerializer.Serialize(result,new JsonSerializerOptions{WriteIndented=true}));Console.WriteLine(JsonSerializer.Serialize(new{result.status,result.conditions,result.oracle_checks}));
    }
}
