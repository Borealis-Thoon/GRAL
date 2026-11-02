using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;
using System.Text.Json;
using System.Text;
using System.Security.Cryptography;

if(args.Length>0 && args[0]=="math-reference")
{
    double[] values={double.NaN,double.NegativeInfinity,double.PositiveInfinity,-2147483649.0,-2147483648.0,-2147483647.9,-1.9,-0.0,0.0,1.9,2147483646.9,2147483647.0,2147483648.0,4294967294.9,4294967295.0,4294967296.0,-9223372036854775808.0,9223372036854775808.0,18446744073709551616.0};
    Console.WriteLine(JsonSerializer.Serialize(new{casts=values.Select(x=>new{i=unchecked((int)x).ToString(),u=unchecked((uint)x).ToString(),l=unchecked((long)x).ToString(),ul=unchecked((ulong)x).ToString()}).ToArray(),abs_negative_zero_bits=BitConverter.SingleToInt32Bits(MathF.Abs(-0.0f))}));
    return;
}
if(args.Length>1 && args[0]=="elementary-reference")
{
    var inputs=JsonSerializer.Deserialize<float[][]>(File.ReadAllText(args[1]))!;
    var outputs=inputs.Select(v=>{
        float log=MathF.Log(v[0]);float root=MathF.Sqrt(-2F*log);float sin=MathF.Sin(v[1]);
        float pow=MathF.Pow(v[2],-0.9F);
        float u=v[2]*(0.2F*pow+0.32F*v[3]+0.18F);u=MathF.Max(u,0.3F);
        float normal=root*sin;
        return new[]{log,root,sin,pow,u,normal,u*normal};
    }).ToArray();
    Console.WriteLine(JsonSerializer.Serialize(outputs));
    return;
}
if(args.Length != 2) throw new ArgumentException("Expected SOURCE_DIRECTORY OUTPUT_DIRECTORY");
var source = Path.GetFullPath(args[0]);
var output = args[1];
var trees = Directory.GetFiles(source, "*.cs").Select(f => CSharpSyntaxTree.ParseText(File.ReadAllText(f), path:f)).ToArray();
var refs = ((string)AppContext.GetData("TRUSTED_PLATFORM_ASSEMBLIES")!).Split(Path.PathSeparator).Select(p=>MetadataReference.CreateFromFile(p));
var compilation = CSharpCompilation.Create("GralSource", trees, refs, new CSharpCompilationOptions(OutputKind.ConsoleApplication,allowUnsafe:true));
var models=trees.ToDictionary(t=>t,t=>compilation.GetSemanticModel(t));
var names = new HashSet<string>{"Zeitschleife.cs","Zeitschleife_nonsteadystate.cs","Transient_Concentration.cs","Intstand.cs"};
var selected = trees.Where(t=>names.Contains(Path.GetFileName(t.FilePath))).ToArray();
var used = selected.SelectMany(t=>t.GetRoot().DescendantNodes().OfType<MemberAccessExpressionSyntax>().Where(m=>m.Expression.ToString()=="Program").Select(m=>m.Name.ToString())).Distinct().Order().ToArray();
var program = compilation.GetTypeByMetadataName("GRAL_2001.Program")!;
var extraMethods=new Dictionary<string,string[]>{
 ["ProgramFunctions.cs"]=new[]{"FloatMax","Pow2","Pow3"},
 ["Intwind.cs"]=new[]{"BinarySearch","IntWindCalculate"}
};
var methods=selected.SelectMany(t=>t.GetRoot().DescendantNodes().OfType<MethodDeclarationSyntax>())
    .Where(m=>m.Parent is not StructDeclarationSyntax && !(m.Identifier.Text=="Calculate" && Path.GetFileName(m.SyntaxTree.FilePath)=="Zeitschleife_nonsteadystate.cs") && !((m.Identifier.Text=="Pd"||m.Identifier.Text=="Erf") && Path.GetFileName(m.SyntaxTree.FilePath)=="Zeitschleife.cs"))
    .Concat(trees.Where(t=>extraMethods.ContainsKey(Path.GetFileName(t.FilePath)))
    .SelectMany(t=>t.GetRoot().DescendantNodes().OfType<MethodDeclarationSyntax>().Where(m=>extraMethods[Path.GetFileName(t.FilePath)].Contains(m.Identifier.Text)))).ToArray();
var structures=selected.SelectMany(t=>t.GetRoot().DescendantNodes().OfType<StructDeclarationSyntax>()).ToArray();
var allSymbols=methods.SelectMany(m=>m.DescendantNodes()).Concat(structures.SelectMany(s=>s.DescendantNodes())).OfType<ExpressionSyntax>()
    .Select(n=>models[n.SyntaxTree].GetSymbolInfo(n).Symbol)
    .OfType<IFieldSymbol>().Where(f=>f.ContainingType.Name=="Program").GroupBy(f=>f.Name).Select(g=>g.First()).OrderBy(f=>f.Name).ToList();
var excluded=new HashSet<string>{"RnGSeed","GridCellReceptors"};
var fields=allSymbols.Where(f=>!excluded.Contains(f.Name)).Select(f=>new{name=f.Name,type=f.Type.ToDisplayString(),cpp=Emitter.Type(f.Type),constant=f.IsConst,value=f.IsConst?f.ConstantValue:null}).ToArray();
var errors=compilation.GetDiagnostics().Where(d=>d.Severity==DiagnosticSeverity.Error).ToArray();
if(errors.Length != 0) throw new InvalidOperationException(string.Join("\n",errors.Select(e=>e.ToString())));
Directory.CreateDirectory(output);
File.WriteAllText(Path.Combine(output,"fields_manifest.json"),JsonSerializer.Serialize(new{schema=1,fields},new JsonSerializerOptions{WriteIndented=true}));
Console.WriteLine("fields "+fields.Length);
Console.WriteLine("nodes "+string.Join(",",selected.SelectMany(t=>t.GetRoot().DescendantNodes().OfType<StatementSyntax>()).Select(n=>n.Kind().ToString()).Distinct().Order()));
Console.WriteLine("locals "+string.Join(",",selected.SelectMany(t=>t.GetRoot().DescendantNodes().OfType<VariableDeclarationSyntax>()).Select(n=>n.Type.ToString()).Distinct().Order()));
Console.WriteLine("errors "+compilation.GetDiagnostics().Count(d=>d.Severity==DiagnosticSeverity.Error));
foreach(var error in compilation.GetDiagnostics().Where(d=>d.Severity==DiagnosticSeverity.Error).Take(12))Console.WriteLine(error);
var emitter=new Emitter(compilation);
var code=new StringBuilder(File.ReadAllText(Path.Combine(AppContext.BaseDirectory,"support.cuh")));
code.AppendLine("struct State {");
foreach(var f in fields.Where(f=>!f.constant))code.AppendLine(f.cpp+" "+f.name+";");
code.AppendLine("unsigned int RnGSeed1; unsigned int RnGSeed2; Arr<int,1> GridRecStart; Arr<int,1> GridRecList; int GridRecRow; bool TraceEnabled; Arr<double,2> Trace; Arr<int,1> TraceIds; Arr<double,3> StepTrace; Arr<double,2> ResidualTrace; int DeviceError; int DeviceErrorPhase; int DeviceErrorParticle; };\nextern \"C\" {__device__ State P;}");
code.AppendLine("__device__ bool CheckParticleFinite(double x,double y,float z,float t,float dt,int phase,int id){if(isfinite(x)&&isfinite(y)&&isfinite(z)&&isfinite(t)&&isfinite(dt))return true;if(atomicCAS(&P.DeviceError,0,1)==0){P.DeviceErrorPhase=phase;P.DeviceErrorParticle=id;}return false;}");
foreach(var s in structures)code.AppendLine("struct "+s.Identifier+";");
foreach(var m in methods)code.AppendLine(emitter.Prototype(m)+";");
code.AppendLine("__device__ float Zeitschleife_Pd(float,float,float,int,int,int){asm(\"trap;\");return 0;}");
code.AppendLine("__device__ bool GridCellLookup(int i,int j,Arr<int,1>& r){if(!P.GridRecStart.p || P.GridRecRow<=0 || i<0 || j<0 || j>=P.GridRecRow)return false;int c=i*P.GridRecRow+j;if(c+1>=P.GridRecStart.d[0])return false;int s=P.GridRecStart[c];int e=P.GridRecStart[c+1];if(e<=s)return false;r.p=P.GridRecList.p+s;r.d[0]=e-s;return true;}");
foreach(var s in structures)code.AppendLine(emitter.Structure(s));
foreach(var m in methods){Console.WriteLine("emit "+Path.GetFileName(m.SyntaxTree.FilePath)+" "+m.Identifier);code.AppendLine(emitter.Method(m));}
code.AppendLine(File.ReadAllText(Path.Combine(AppContext.BaseDirectory,"entries.cuh")));
File.WriteAllText(Path.Combine(output,"generated.cu"),code.ToString());
var provenance=methods.Select(m=>m.SyntaxTree.FilePath).Concat(structures.Select(s=>s.SyntaxTree.FilePath)).Distinct().Order().Select(p=>new{path=p,sha256=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(p))).ToLowerInvariant()}).ToArray();
File.WriteAllText(Path.Combine(output,"translation_manifest.json"),JsonSerializer.Serialize(new{
    schema=1,source_files=provenance,
    methods=methods.Select(m=>new{file=m.SyntaxTree.FilePath,line=m.GetLocation().GetLineSpan().StartLinePosition.Line+1,name=m.Identifier.Text}),
    generated_sha256=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(Path.Combine(output,"generated.cu")))).ToLowerInvariant(),
    transformations=new[]{"symbol-aware local declaration hoisting for CUDA goto legality","jagged arrays to flat row-major views","shared concentration and receptor additions use CUDA atomic operations","typed Math/MathF operations with CUDA elementary functions",".NET 9+ saturating FP-to-integer casts","fixed situation RNG seeds preserved; overwritten clock seed defaults use zero","receptor dictionary lookup emitted as CSR scan","unsupported deposition entry path traps","optional fresh and residual tracing does not change particle state","nonfinite position/time/timestep aborts entire GPU run without exporting results"},
    accuracy_status="not yet validated against full-engine fields; CUDA compilation is not numerical equivalence"
},new JsonSerializerOptions{WriteIndented=true}));
