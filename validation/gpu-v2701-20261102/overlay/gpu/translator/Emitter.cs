using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;
using System.Text;
using System.Globalization;

sealed class Emitter
{
    readonly CSharpCompilation compilation;
    SemanticModel model = null!;
    Dictionary<ISymbol,string> locals = new(SymbolEqualityComparer.Default);
    readonly List<string> declarations = new();
    int temporary;
    bool traceFresh;
    bool traceResidual;
    ExpressionStatementSyntax? provisionalTimeStep, limitedTimeStep;
    static readonly HashSet<string> particleState = new(){"xcoord_nteil","ycoord_nteil","zcoord_nteil","auszeit","idt"};
    public Emitter(CSharpCompilation c) { compilation=c; }
    public static string Type(ITypeSymbol t)
    {
        int rank=0;
        while(t is IArrayTypeSymbol a){rank+=a.Rank;t=a.ElementType;}
        if(t is INamedTypeSymbol n && (n.Name=="Span" || n.Name=="List")){rank++;t=n.TypeArguments[0];}
        string scalar=t.SpecialType switch {
            SpecialType.System_Boolean=>"bool",SpecialType.System_Byte=>"unsigned char",SpecialType.System_Int16=>"short",
            SpecialType.System_Int32=>"int",SpecialType.System_UInt32=>"unsigned int",SpecialType.System_Int64=>"long long",
            SpecialType.System_UInt64=>"unsigned long long",SpecialType.System_Single=>"float",SpecialType.System_Double=>"double",
            SpecialType.System_Void=>"void",_=>t.Name};
        if(t is INamedTypeSymbol nt && nt.IsTupleType)scalar="Tuple"+nt.TupleElements.Length+"<"+string.Join(",",nt.TupleElements.Select(x=>Type(x.Type)))+">";
        return rank>0?$"Arr<{scalar},{rank}>":scalar;
    }
    static string Function(IMethodSymbol m)=>m.IsStatic?m.ContainingType.Name+"_"+m.Name:m.Name;
    static string Constant(IFieldSymbol f)
    {
        object? x=f.ConstantValue;
        if(x is bool b)return b?"true":"false";
        if(x is float a){if(float.IsNaN(a))return "__int_as_float((int)0xFFC00000)";var s=a.ToString("R",CultureInfo.InvariantCulture);return s+(s.Contains('.')||s.Contains('E')?"":".0")+"f";}
        if(x is double d)return d.ToString("R",CultureInfo.InvariantCulture);
        if(x is uint u)return u.ToString()+"u";
        if(x is ulong ul)return ul.ToString()+"ull";
        return Convert.ToString(x,CultureInfo.InvariantCulture)??"0";
    }
    string Ident(IdentifierNameSyntax n)
    {
        var sym=model.GetSymbolInfo(n).Symbol;
        if(sym!=null && locals.TryGetValue(sym,out var local))return local;
        if(sym is IFieldSymbol f){if(f.IsConst)return "("+Constant(f)+")";if(f.ContainingType.Name=="Program")return "P."+f.Name;}
        if(sym is IMethodSymbol m)return Function(m);
        return n.Identifier.Text;
    }
    string Call(InvocationExpressionSyntax n)
    {
        var method=model.GetSymbolInfo(n).Symbol as IMethodSymbol;
        var name=n.Expression.ToString();
        var args=n.ArgumentList.Arguments.Select(x=>Expr(x.Expression)).ToArray();
        if(name.EndsWith(".GetUpperBound"))return Expr(((MemberAccessExpressionSyntax)n.Expression).Expression)+".upper("+args[0]+")";
        if(name.EndsWith(".GetLength"))return Expr(((MemberAccessExpressionSyntax)n.Expression).Expression)+".d["+args[0]+"]";
        if(name=="Program.GridCellReceptors.TryGetValue"){var key=(TupleExpressionSyntax)n.ArgumentList.Arguments[0].Expression;return "GridCellLookup("+Expr(key.Arguments[0].Expression)+","+Expr(key.Arguments[1].Expression)+","+args[1]+")";}
        if(name.EndsWith(".Clear"))return Expr(((MemberAccessExpressionSyntax)n.Expression).Expression)+".clear()";
        if(name=="BitConverter.SingleToInt32Bits")return "__float_as_int("+args[0]+")";
        if(name.EndsWith(".IsFinite"))return "isfinite("+args[0]+")";
        if(name.StartsWith("System.Threading.Interlocked.") || name.StartsWith("Interlocked."))
        {
            var kind=name.Split('.').Last();
            return kind switch {
                "Increment"=>"atomic_inc("+"&("+args[0]+"))",
                "Add"=>"atomic_add(&("+args[0]+"),"+args[1]+")",
                "Exchange"=>"atomic_exchange(&("+args[0]+"),"+args[1]+")",
                "CompareExchange"=>"atomic_compare(&("+args[0]+"),"+args[2]+","+args[1]+")",
                _=>throw new NotSupportedException(name)};
        }
        if(name.StartsWith("MathF.") || name.StartsWith("Math."))
        {
            string op=name.Split('.').Last();
            string fn=op switch {"Abs"=>"gral_abs","Min"=>"gral_min","Max"=>"gral_max","Clamp"=>"gral_clamp","Sign"=>"gral_sign","Round"=>"gral_round",_=>op.ToLowerInvariant()};
            if(op is "Sqrt" or "Sin" or "Cos" or "Log" or "Exp" or "Pow")
                fn+=(method?.ReturnType.SpecialType==SpecialType.System_Single?"f":"");
            // CUDA overload resolution follows the C++ argument type. Preserve C#'s
            // implicit parameter conversions, including Math(double) fed float expressions.
            if(method!=null)
                args=args.Select((a,i)=>"("+Type(method.Parameters[Math.Min(i,method.Parameters.Length-1)].Type)+")("+a+")").ToArray();
            return fn+"("+string.Join(",",args)+")";
        }
        string callee;
        if(method?.IsStatic==true)callee=Function(method);
        else callee=Expr(n.Expression);
        return callee+"("+string.Join(",",args)+")";
    }
    string Assign(AssignmentExpressionSyntax n)
    {
        if(n.Left is TupleExpressionSyntax tuple)
        {
            string temp="tuple_tmp_"+(temporary++);
            var tt=model.GetTypeInfo(n.Right).Type!;
            declarations.Add(Type(tt)+" "+temp+"{};");
            return temp+" = "+Expr(n.Right)+"; "+string.Join("; ",tuple.Arguments.Select((a,i)=>Expr(a.Expression)+" = "+temp+".v"+i));
        }
        var left=Expr(n.Left);var right=Expr(n.Right);
        if(n.IsKind(SyntaxKind.AddAssignmentExpression) && n.Left is ElementAccessExpressionSyntax && IsShared(n.Left))
            return "atomic_add(&("+left+"),"+right+")";
        if(n.Left is ThisExpressionSyntax && n.Right.IsKind(SyntaxKind.DefaultLiteralExpression))return "*this = {}";
        return left+" "+n.OperatorToken.Text+" "+right;
    }
    bool IsShared(ExpressionSyntax e)
    {
        string text=e.ToString();
        return text.StartsWith("Program.EmissionPerSG") || text.StartsWith("Program.Log") ||
            new[]{"conz3dD_L","conz3d_L","conz5d_L","depo_L","conzsum_L","conz3dp_L","conz3dm_L","recmit_L"}.Any(x=>text.StartsWith(x+"["));
    }
    string Expr(ExpressionSyntax? e)
    {
        if(e==null)return "";
        switch(e)
        {
            case IdentifierNameSyntax n:return Ident(n);
            case LiteralExpressionSyntax n:
                if(n.IsKind(SyntaxKind.NullLiteralExpression))return "nullptr";
                if(n.IsKind(SyntaxKind.DefaultLiteralExpression))return "{}";
                var lit=n.Token.Text.Replace("UL","ull").Replace("uL","ull");
                if(System.Text.RegularExpressions.Regex.IsMatch(lit,@"^\d+[fF]$"))lit=lit[..^1]+".0f";
                return lit;
            case ParenthesizedExpressionSyntax n:return "("+Expr(n.Expression)+")";
            case BinaryExpressionSyntax n:return Expr(n.Left)+" "+n.OperatorToken.Text+" "+Expr(n.Right);
            case PrefixUnaryExpressionSyntax n:return n.OperatorToken.Text+Expr(n.Operand);
            case PostfixUnaryExpressionSyntax n:return Expr(n.Operand)+n.OperatorToken.Text;
            case CastExpressionSyntax n:
                var target=model.GetTypeInfo(n.Type).Type!;
                var from=model.GetTypeInfo(n.Expression).Type!;
                if(from.SpecialType is SpecialType.System_Single or SpecialType.System_Double &&
                    target.SpecialType is SpecialType.System_Int32 or SpecialType.System_UInt32 or SpecialType.System_Int64 or SpecialType.System_UInt64)
                    return "cs_cast<"+Type(target)+">("+Expr(n.Expression)+")";
                return "("+Type(target)+")("+Expr(n.Expression)+")";
            case ConditionalExpressionSyntax n:return Expr(n.Condition)+" ? "+Expr(n.WhenTrue)+" : "+Expr(n.WhenFalse);
            case AssignmentExpressionSyntax n:return Assign(n);
            case InvocationExpressionSyntax n:return Call(n);
            case MemberAccessExpressionSyntax n:
                if(n.ToString()=="Environment.TickCount")return "0";
                if(n.ToString()=="Program.RnGSeed.Seed1")return "P.RnGSeed1";
                if(n.ToString()=="Program.RnGSeed.Seed2")return "P.RnGSeed2";
                if(n.ToString()=="Program.GridCellReceptors")return "P.GridRecStart";
                var sym=model.GetSymbolInfo(n).Symbol;
                if(sym is IFieldSymbol f){if(f.IsConst)return "("+Constant(f)+")";if(f.ContainingType.Name=="Program")return "P."+f.Name;}
                if(sym is IMethodSymbol met && met.IsStatic)return Function(met);
                if(n.Name.ToString()=="Length")return Expr(n.Expression)+".size()";
                if(n.Name.ToString()=="Count")return Expr(n.Expression)+".size()";
                return Expr(n.Expression)+"."+n.Name;
            case ElementAccessExpressionSyntax n:
                var a=n.ArgumentList.Arguments.Select(x=>Expr(x.Expression)).ToArray();
                return Expr(n.Expression)+(a.Length==1?"["+a[0]+"]":"("+string.Join(",",a)+")");
            case ObjectCreationExpressionSyntax n:return Type(model.GetTypeInfo(n).Type!)+"("+string.Join(",",n.ArgumentList!.Arguments.Select(x=>Expr(x.Expression)))+")";
            case TupleExpressionSyntax n:return "{"+string.Join(",",n.Arguments.Select(x=>Expr(x.Expression)))+"}";
            case DeclarationExpressionSyntax n:
                var d=(SingleVariableDesignationSyntax)n.Designation;
                return locals[model.GetDeclaredSymbol(d)!];
            case ThisExpressionSyntax:return "(*this)";
            case DefaultExpressionSyntax:return "{}";
            default:throw new NotSupportedException("expression "+e.Kind()+": "+e);
        }
    }
    string Variables(VariableDeclarationSyntax n)
    {
        var b=new StringBuilder();
        foreach(var v in n.Variables)
        {
            var symbol=(ILocalSymbol)model.GetDeclaredSymbol(v)!;
            var name=locals[symbol];
            if(v.Initializer!=null)
            {
                if(symbol.Type is INamedTypeSymbol nt && nt.Name=="Span")
                {
                    string count=symbol.Type.ToString()!.Contains("double")?"P.ReceptorNumber+1":"P.NS";
                    b.Append(name+" = {"+name+"_storage,{"+count+"}};");
                }
                else b.Append(name+" = "+Expr(v.Initializer.Value)+";");
            }
        }
        return b.ToString();
    }
    string FiniteGuard()
    {
        if(!traceFresh && !traceResidual)return "";
        string Local(string name)=>locals.First(x=>x.Key.Name==name).Value;
        string values=string.Join(",",new[]{"xcoord_nteil","ycoord_nteil","zcoord_nteil","auszeit","idt"}.Select(Local));
        return "if(!CheckParticleFinite("+values+","+(traceFresh?"1,nteil":"2,trace_index")+"))return;";
    }
    static bool IsParticleState(ExpressionSyntax expression)=>expression is IdentifierNameSyntax identifier && particleState.Contains(identifier.Identifier.Text);
    static bool UpdatesParticleState(ExpressionSyntax expression)=>expression switch {
        AssignmentExpressionSyntax assignment=>IsParticleState(assignment.Left),
        PrefixUnaryExpressionSyntax prefix=>IsParticleState(prefix.Operand),
        PostfixUnaryExpressionSyntax postfix=>IsParticleState(postfix.Operand),
        InvocationExpressionSyntax call=>call.ArgumentList.Arguments.Any(a=>!a.RefKindKeyword.IsKind(SyntaxKind.None) && IsParticleState(a.Expression)),
        _=>false
    };
    void ValidateTimeStepAnchors(BaseMethodDeclarationSyntax method)
    {
        provisionalTimeStep=null;limitedTimeStep=null;
        if(!traceFresh && !traceResidual)return;
        const string initial="idt = 0.1F * varw / eps;";
        const string pointLimit="if (SourceType == Consts.SourceTypePoint && auszeit < 20) { idt = MathF.Min(0.2F, idt); if (horPSExitDistance > 0 && auszeit < 3) { idt = MathF.Round(MathF.Max(0.01F, MathF.Min(0.2F, 0.5F / (5 + horPSPlumeVelocity))), 3); } }";
        const string limit="float idtt = 0.5F * Math.Min(Program.GralDx, FFGridX) / (windge + MathF.Sqrt(Program.Pow2(velxold) + Program.Pow2(velyold))); if (idtt < idt) { idt = idtt; } Math.Clamp(idt, 0.1F, 4F);";
        var expected=(BlockSyntax)SyntaxFactory.ParseStatement("{"+initial+(traceFresh?pointLimit:"")+limit+"}");
        var matches=method.DescendantNodes().OfType<ExpressionStatementSyntax>()
            .Where(s=>SyntaxFactory.AreEquivalent(s,expected.Statements[0])).ToArray();
        if(matches.Length!=1 || matches[0].Parent is not BlockSyntax block)
            throw new InvalidOperationException("Frozen V2701 time-step initial anchor changed");
        int start=block.Statements.IndexOf(matches[0]);
        if(start+expected.Statements.Count>block.Statements.Count ||
            expected.Statements.Where((statement,index)=>!SyntaxFactory.AreEquivalent(statement,block.Statements[start+index])).Any())
            throw new InvalidOperationException("Frozen V2701 time-step limiter block changed");
        provisionalTimeStep=matches[0];
        limitedTimeStep=(ExpressionStatementSyntax)block.Statements[start+expected.Statements.Count-1];
    }
    string Statement(StatementSyntax s)
    {
        switch(s)
        {
            case BlockSyntax n:return "{\n"+string.Join("\n",n.Statements.Select(Statement))+"\n}";
            case LocalDeclarationStatementSyntax n:
                return Variables(n.Declaration)+(n.Declaration.Variables.Any(v=>particleState.Contains(v.Identifier.Text))?FiniteGuard():"");
            case ExpressionStatementSyntax n:
                var expression=Expr(n.Expression)+";";
                // The pinned limiter can recover +Infinity from varw/eps before idt is consumed.
                bool guarded=(traceFresh || traceResidual) &&
                    ((n.Expression.ToString()=="++timestep_number" || UpdatesParticleState(n.Expression)) &&
                     !ReferenceEquals(n,provisionalTimeStep) || ReferenceEquals(n,limitedTimeStep));
                if(guarded)
                {
                    expression+=FiniteGuard();
                }
                if(traceResidual && n.Expression is InvocationExpressionSyntax inv && inv.Expression.ToString()=="ResidualSeeds")
                {
                    string Local(string name)=>locals.First(x=>x.Key.Name==name).Value;
                    var values=new[]{"i","j","k","SG","splitIndex","m_w","m_z"};
                    expression+="if(trace_slot>=0){"+string.Join("",values.Select((v,i)=>"P.ResidualTrace(trace_slot,"+i+")="+Local(v)+";"))+"}";
                }
                if(traceFresh && n.Expression.ToString()=="++timestep_number")
                {
                    string Local(string name)=>locals.First(x=>x.Key.Name==name).Value;
                    var values=new[]{"xcoord_nteil","ycoord_nteil","zcoord_nteil","auszeit","idt","velxold","velyold","velzold","m_w","m_z","FFCellX","FFCellY","IndexK","ObLength","roughZ0","windge"};
                    string index=Local("timestep_number")+"-1";
                    expression+="if(trace_slot>=0 && "+Local("timestep_number")+"<=P.StepTrace.d[1]){"+
                        string.Join("",values.Select((v,i)=>"P.StepTrace[trace_slot]["+index+"]["+i+"]="+Local(v)+";"))+"}";
                }
                return guarded || n.Expression is AssignmentExpressionSyntax assignment && assignment.Left is TupleExpressionSyntax ? "{"+expression+"}":expression;
            case ReturnStatementSyntax n:
                var trace="";
                if(traceFresh)
                {
                    string Local(string name)=>locals.First(x=>x.Key.Name==name).Value;
                    var values=new[]{"xcoord_nteil","ycoord_nteil","zcoord_nteil","auszeit","timestep_number","m_w","m_z","masse"};
                    trace="if(P.TraceEnabled && P.Trace.p && nteil<P.Trace.d[0]){"+string.Join("",values.Select((v,i)=>"P.Trace(nteil,"+i+")="+Local(v)+";"))+"}\n";
                }
                if(traceResidual)
                {
                    string Local(string name)=>locals.First(x=>x.Key.Name==name).Value;
                    var values=new[]{"xcoord_nteil","ycoord_nteil","zcoord_nteil","auszeit","timestep_number","m_w","m_z","masse"};
                    trace="if(trace_slot>=0){"+string.Join("",values.Select((v,i)=>"P.ResidualTrace(trace_slot,"+(i+7)+")="+Local(v)+";"))+"P.ResidualTrace(trace_slot,15)=1;}\n";
                }
                return traceFresh||traceResidual?"{"+FiniteGuard()+trace+"return "+Expr(n.Expression)+";}":"return "+Expr(n.Expression)+";";
            case IfStatementSyntax n:return "if ("+Expr(n.Condition)+") "+Statement(n.Statement)+(n.Else==null?"":" else "+Statement(n.Else.Statement));
            case WhileStatementSyntax n:return "while ("+Expr(n.Condition)+") "+Statement(n.Statement);
            case ForStatementSyntax n:
                var init=n.Declaration==null?string.Join(",",n.Initializers.Select(Expr)):Variables(n.Declaration).TrimEnd(';');
                return "for ("+init+";"+Expr(n.Condition)+";"+string.Join(",",n.Incrementors.Select(Expr))+") "+Statement(n.Statement);
            case LockStatementSyntax n:return Statement(n.Statement);
            case BreakStatementSyntax:return "break;";
            case CheckedStatementSyntax n:return Statement(n.Block);
            case ForEachStatementSyntax n:
                var fe=locals[model.GetDeclaredSymbol(n)!];var it="fe_"+fe;var src=Expr(n.Expression);
                return "for (int "+it+"=0;"+it+"<"+src+".size();"+it+"++) {\n"+fe+"="+src+"["+it+"];\n"+Statement(n.Statement)+"\n}";
            case GotoStatementSyntax n:return "goto "+n.Expression+";";
            case LabeledStatementSyntax n:return n.Identifier+": ;\n"+Statement(n.Statement);
            default:throw new NotSupportedException("statement "+s.Kind());
        }
    }
    void Prepare(BaseMethodDeclarationSyntax node)
    {
        model=compilation.GetSemanticModel(node.SyntaxTree);locals.Clear();declarations.Clear();temporary=0;
        traceFresh=node is MethodDeclarationSyntax method && method.Identifier.Text=="Calculate" && Path.GetFileName(node.SyntaxTree.FilePath)=="Zeitschleife.cs";
        traceResidual=node is MethodDeclarationSyntax residual && residual.Identifier.Text=="ParticleDriver" && Path.GetFileName(node.SyntaxTree.FilePath)=="Zeitschleife_nonsteadystate.cs";
        ValidateTimeStepAnchors(node);
        foreach(var p in node.ParameterList.Parameters){var sy=model.GetDeclaredSymbol(p);if(sy!=null)locals[sy]=p.Identifier.Text;}
        foreach(var n in node.DescendantNodes())
        {
            var symbol=n switch {VariableDeclaratorSyntax v=>model.GetDeclaredSymbol(v),SingleVariableDesignationSyntax d=>model.GetDeclaredSymbol(d),ForEachStatementSyntax f=>model.GetDeclaredSymbol(f),_=>(ISymbol?)null};
            if(symbol is not ILocalSymbol l || locals.ContainsKey(l))continue;
            string name=l.Name+"_"+locals.Count;locals[l]=name;
            if(l.Type is INamedTypeSymbol nt && nt.Name=="Span")
            {
                string scalar=Type(nt.TypeArguments[0]);int count=scalar=="double"?51:9;
                declarations.Add(scalar+" "+name+"_storage["+count+"]{};");
            }
            declarations.Add(Type(l.Type)+" "+name+"{};");
        }
    }
    string Parameters(IMethodSymbol method)=>string.Join(",",method.Parameters.Select(p=>Type(p.Type)+(p.RefKind!=RefKind.None?"&":"")+" "+p.Name));
    public string Prototype(MethodDeclarationSyntax n)
    {
        var m=(IMethodSymbol)compilation.GetSemanticModel(n.SyntaxTree).GetDeclaredSymbol(n)!;
        var suffix=m.Name=="ParticleDriver" && m.ContainingType.Name=="ZeitschleifeNonSteadyState"?",int trace_index":"";
        return "__device__ "+Type(m.ReturnType)+" "+Function(m)+"("+Parameters(m)+suffix+")";
    }
    public string Method(MethodDeclarationSyntax n)
    {
        Prepare(n);string body=n.Body!=null?string.Join("\n",n.Body.Statements.Select(Statement)):"return "+Expr(n.ExpressionBody!.Expression)+";";
        if(traceFresh)body="int trace_slot=-1;if(P.TraceEnabled && P.TraceIds.p){for(int qi=0;qi<P.TraceIds.d[0];qi++)if(P.TraceIds[qi]==nteil)trace_slot=qi;}\n"+body;
        if(traceResidual)body="int trace_slot=(P.TraceEnabled && P.ResidualTrace.p && trace_index>=0 && trace_index<P.ResidualTrace.d[0])?trace_index:-1;\n"+body;
        return Prototype(n)+" {\n"+string.Join("\n",declarations)+"\n"+body+"\n}\n";
    }
    public string Structure(StructDeclarationSyntax n)
    {
        model=compilation.GetSemanticModel(n.SyntaxTree);
        var b=new StringBuilder("struct "+n.Identifier+" {\n");
        foreach(var f in n.Members.OfType<FieldDeclarationSyntax>())foreach(var v in f.Declaration.Variables)
        {var field=(IFieldSymbol)model.GetDeclaredSymbol(v)!;b.AppendLine(Type(field.Type)+" "+field.Name+"{};");}
        b.AppendLine("__device__ "+n.Identifier+"() = default;");
        foreach(var ctor in n.Members.OfType<ConstructorDeclarationSyntax>())
        {
            Prepare(ctor);var m=(IMethodSymbol)model.GetDeclaredSymbol(ctor)!;
            string body=string.Join("\n",ctor.Body!.Statements.Select(Statement));
            b.AppendLine("__device__ "+n.Identifier+"("+Parameters(m)+") {"+string.Join("\n",declarations)+body+"}");
        }
        foreach(var m in n.Members.OfType<MethodDeclarationSyntax>())b.Append(Method(m));
        return b.Append("};\n").ToString();
    }
}
