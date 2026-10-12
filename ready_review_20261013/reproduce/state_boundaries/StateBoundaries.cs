using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
class StateBoundaries
{
    const BindingFlags Flags=BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic;
    static int checks;
    static void Check(bool ok,string label){if(!ok)throw new Exception(label);Interlocked.Increment(ref checks);}
    static bool DoubleFinite(double x)=>(BitConverter.DoubleToUInt64Bits(x)&0x7ff0000000000000UL)!=0x7ff0000000000000UL;
    static bool FloatFinite(float x)=>(BitConverter.SingleToUInt32Bits(x)&0x7f800000U)!=0x7f800000U;
    static ulong Mix(ulong value){unchecked{value=(value^(value>>30))*0xbf58476d1ce4e5b9UL;value=(value^(value>>27))*0x94d049bb133111ebUL;return value^(value>>31);}}
    static void Main(string[] args)
    {
        var asm=new AssemblyLoadContext("state",false).LoadFromAssemblyPath(Path.GetFullPath(args[0]));
        var p=asm.GetType("GRAL_2001.Program");
        var counter=p.GetField("NonFiniteParticleCount",Flags);
        var valid=p.GetMethod("ParticleStateIsFinite",Flags).CreateDelegate<Func<double,double,float,double,float,bool>>();
        void Set(string name,object value){var field=p.GetField(name,Flags);field.SetValue(null,value==null||field.FieldType.IsInstanceOfType(value)?value:Convert.ChangeType(value,field.FieldType));}
        var records=new List<object>();
        foreach(int workers in new[]{1,2,8})
        {
            counter.SetValue(null,0L);long expectedRejected=0;
            Parallel.For(0,32768,new ParallelOptions{MaxDegreeOfParallelism=workers},i=>
            {
                ulong xb=Mix((ulong)i+1),yb=Mix((ulong)i+32769),mb=Mix((ulong)i+65537);
                uint zb=(uint)Mix((ulong)i+98305),dtb=(uint)Mix((ulong)i+131073);
                if(i%19==0)xb|=0x7ff0000000000000UL;
                if(i%23==0)yb|=0x7ff0000000000000UL;
                if(i%29==0)mb|=0x7ff0000000000000UL;
                if(i%31==0)zb|=0x7f800000U;
                if(i%37==0)dtb|=0x7f800000U;
                double x=BitConverter.UInt64BitsToDouble(xb),y=BitConverter.UInt64BitsToDouble(yb),m=BitConverter.UInt64BitsToDouble(mb);
                float z=BitConverter.UInt32BitsToSingle(zb),dt=BitConverter.UInt32BitsToSingle(dtb);
                bool expected=DoubleFinite(x)&&DoubleFinite(y)&&FloatFinite(z)&&DoubleFinite(m)&&FloatFinite(dt);
                Check(valid(x,y,z,m,dt)==expected,"Bit-pattern classification differs");
                if(!expected)Interlocked.Increment(ref expectedRejected);
            });
            long rejected=(long)counter.GetValue(null);Check(rejected==expectedRejected,"Atomic counter differs from independent bit classification");
            records.Add(new{workers,states=32768,rejected});
        }
        Set("DXK",20);Set("DYK",20);Set("GridVolume",1);Set("TAUS",30);Set("DZK_Trans",new float[]{0,10});
        // An attempted child-particle entry would access this missing grid and throw.
        Set("AHK",null);
        var calculate=asm.GetType("GRAL_2001.ZeitschleifeNonSteadyState").GetMethod("Calculate",Flags);
        int entryCases=0;
        foreach(float bad in new[]{float.NaN,float.PositiveInfinity,float.NegativeInfinity})
        foreach(double reference in new[]{0d,1d,double.MaxValue,double.NaN,double.PositiveInfinity,double.NegativeInfinity})
        {
            Set("ParticleMassMean",reference);counter.SetValue(null,0L);
            calculate.Invoke(null,new object[]{1,1,1,0,bad});
            Check((long)counter.GetValue(null)==1,"Non-finite cell must be rejected once before child tracking");entryCases++;
        }
        File.WriteAllText(args[1],JsonSerializer.Serialize(new{status="pass",checks,helper_cases=98304,bit_pattern_records=records,residual_entry_cases=entryCases,scope="Actual merged #66 helper and residual Calculate method. Independent IEEE exponent-bit oracle; component-only tests."},new JsonSerializerOptions{WriteIndented=true}));
        Console.WriteLine("[PASS] "+checks+" checks");
    }
}
