using System;
static class ExtractedRngEndpoint
{
    private const float Pi2F = 2F * MathF.PI;
    private const float RNG_Const = 2.328306435454494e-10F;
    public static float Normal(uint first,uint second,out float uniform)
    {
        uint u_rg=first;
        float u1_rg;
        u1_rg = (u_rg + 1) * RNG_Const;
        uniform=u1_rg;
        u_rg=second;
        float zahl1;
        zahl1 = MathF.Sqrt(-2F * MathF.Log(u1_rg)) * MathF.Sin(Pi2F * (u_rg + 1) * RNG_Const);
        return zahl1;
    }
}
