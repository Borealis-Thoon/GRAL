using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Collections;

class SourceSeriesReaderTest
{
    static int Main(string[] args)
    {
        var assembly = Assembly.Load("GRAL");
        var reader = Activator.CreateInstance(assembly.GetType("GRAL_2001.ReadSourceTimeSeries", true));
        var method = reader.GetType().GetMethod("ReadTimeSeries");
        var lookup = assembly.GetType("GRAL_2001.GetTransientTimeSeriesIndex", true).GetMethod("GetIndex", BindingFlags.Static | BindingFlags.Public);
        assembly.GetType("GRAL_2001.Program", true).GetField("ISTATIONAER").SetValue(null, 0);
        foreach (var spec in new[] {
            ("TimeSeriesPointSourceTemp.txt", "point_temp", "Temp@_", new float[] { 0, 20, 80, 40 }, "point.dat"),
            ("TimeSeriesPointSourceVel.txt", "point_vel", "Vel@_", new float[] { .05f, .2f, 6, .05f }, "point.dat"),
            ("TimeSeriesPortalSourceTemp.txt", "portal_temp", "Temp@_", new float[] { 0, 10, 20, 5 }, "portals.dat"),
            ("TimeSeriesPortalSourceVel.txt", "portal_vel", "Vel@_", new float[] { .05f, .2f, 8, 2 }, "portals.dat") })
        {
            object[] parameters = { null, Path.Combine(args[0], spec.Item1) };
            if (!(bool)method.Invoke(reader, parameters)) throw new Exception("Reader rejected " + spec.Item1);
            var list = (IList)parameters[0];
            if (list.Count != 1) throw new Exception("Column count " + spec.Item1);
            object col = list[0];
            string name = (string)col.GetType().GetProperty("Name").GetValue(col);
            float[] values = (float[])col.GetType().GetProperty("Value").GetValue(col);
            if (name != spec.Item2 || values.Length != 5 || !values.Take(4).SequenceEqual(spec.Item4)) throw new Exception("Values " + spec.Item1);
            string[] row = File.ReadAllLines(Path.Combine(args[0], spec.Item5))[2].Split(',');
            if ((int)lookup.Invoke(null, new object[] { list, spec.Item3, row }) != 0) throw new Exception("Source linkage " + spec.Item1);
            Console.WriteLine("PASS " + spec.Item1 + " rows=4 allocated=5 link=0");
        }
        return 0;
    }
}
