using System.Reflection;
using System.Text.Json;

var assembly = Assembly.LoadFrom(Path.GetFullPath(args[0]));
var program = assembly.GetType("GRAL_2001.Program", true)!;
var residual = assembly.GetType("GRAL_2001.ZeitschleifeNonSteadyState", true)!;
var method = residual.GetMethod("ResidualSeeds", BindingFlags.Static | BindingFlags.NonPublic)!;
var fixtures = new uint[][] {
    new uint[] {1,1,1,1,0,0,521288629,2232121},
    new uint[] {2,31,57,19,35,1,521288629,2232121},
    new uint[] {36,150,120,30,35,99999,4294967294,4294967293},
    new uint[] {4,8,9,10,0,0,0,0},
    new uint[] {4,8,9,10,1,0,0,0},
    new uint[] {4,8,9,10,0,1,0,0},
};
var results = fixtures.Select(f => {
    program.GetField("IWET", BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic)!.SetValue(null, (int)f[0]);
    uint w=unchecked(f[6]+f[1]+f[2]), z=unchecked(f[7]+2*f[1]);
    object[] input={(int)f[1],(int)f[2],(int)f[3],(int)f[4],(int)f[5],w,z};
    method.Invoke(null,input);
    return new {fixture=f,seeds=new[]{(uint)input[5],(uint)input[6]}};
}).ToArray();
Console.WriteLine(JsonSerializer.Serialize(results));
