using System;
using System.Collections.Generic;
using System.Threading;
using Program = ExitProbeProgram;
static class ExtractedParticleExit
{
    public static bool Guard_0(double xcoord_nteil, double ycoord_nteil, float zcoord_nteil, double masse, float idt, double mass_real)
    {
        bool continued = false;
        int SG_nteil = 0;
        double[] ReceptorConcentration = { 0, .25, 1.5 };
        double epsilonW_Masse = masse;
        if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, masse, 0.1F))
            {
                goto REMOVE_PARTICLE;
            }
        continued = true;
    REMOVE_PARTICLE:
            // Add local receptor concentrations to receptor array and store maximum concentration part for each receptor
            if (Program.ReceptorsAvailable)
            {
                for (int ii = 1; ii < ReceptorConcentration.Length; ii++)
                {
                    double recconc = ReceptorConcentration[ii];
                    if (recconc > 0)
                    {
                        double[] recmit_L = Program.ReceptorConc[ii];
                        lock (recmit_L)
                        {
                            recmit_L[SG_nteil] += recconc;
                        }

                        if (recconc > Program.ReceptorParticleMaxConc[ii][SG_nteil])
                        {
                            Interlocked.Exchange(ref Program.ReceptorParticleMaxConc[ii][SG_nteil], recconc);
                        }
                    }
                }
            }

        return continued;
    }
    public static bool Guard_1(double xcoord_nteil, double ycoord_nteil, float zcoord_nteil, double masse, float idt, double mass_real)
    {
        bool continued = false;
        int SG_nteil = 0;
        double[] ReceptorConcentration = { 0, .25, 1.5 };
        double epsilonW_Masse = masse;
        if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, masse, 0.1F))
                {
                    goto REMOVE_PARTICLE;
                }
        continued = true;
    REMOVE_PARTICLE:
            // Add local receptor concentrations to receptor array and store maximum concentration part for each receptor
            if (Program.ReceptorsAvailable)
            {
                for (int ii = 1; ii < ReceptorConcentration.Length; ii++)
                {
                    double recconc = ReceptorConcentration[ii];
                    if (recconc > 0)
                    {
                        double[] recmit_L = Program.ReceptorConc[ii];
                        lock (recmit_L)
                        {
                            recmit_L[SG_nteil] += recconc;
                        }

                        if (recconc > Program.ReceptorParticleMaxConc[ii][SG_nteil])
                        {
                            Interlocked.Exchange(ref Program.ReceptorParticleMaxConc[ii][SG_nteil], recconc);
                        }
                    }
                }
            }

        return continued;
    }
    public static bool Guard_2(double xcoord_nteil, double ycoord_nteil, float zcoord_nteil, double masse, float idt, double mass_real)
    {
        bool continued = false;
        int SG_nteil = 0;
        double[] ReceptorConcentration = { 0, .25, 1.5 };
        double epsilonW_Masse = masse;
        if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, masse, idt))
                {
                    goto REMOVE_PARTICLE;
                }
        continued = true;
    REMOVE_PARTICLE:
            // Add local receptor concentrations to receptor array and store maximum concentration part for each receptor
            if (Program.ReceptorsAvailable)
            {
                for (int ii = 1; ii < ReceptorConcentration.Length; ii++)
                {
                    double recconc = ReceptorConcentration[ii];
                    if (recconc > 0)
                    {
                        double[] recmit_L = Program.ReceptorConc[ii];
                        lock (recmit_L)
                        {
                            recmit_L[SG_nteil] += recconc;
                        }

                        if (recconc > Program.ReceptorParticleMaxConc[ii][SG_nteil])
                        {
                            Interlocked.Exchange(ref Program.ReceptorParticleMaxConc[ii][SG_nteil], recconc);
                        }
                    }
                }
            }

        return continued;
    }
    public static bool Guard_3(double xcoord_nteil, double ycoord_nteil, float zcoord_nteil, double masse, float idt, double mass_real)
    {
        bool continued = false;
        int SG_nteil = 0;
        double[] ReceptorConcentration = { 0, .25, 1.5 };
        double epsilonW_Masse = masse;
        if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, masse, idt))
                {
                    goto REMOVE_PARTICLE;
                }
        continued = true;
    REMOVE_PARTICLE:
            // Add local receptor concentrations to receptor array and store maximum concentration part for each receptor
            if (Program.ReceptorsAvailable)
            {
                for (int ii = 1; ii < ReceptorConcentration.Length; ii++)
                {
                    double recconc = ReceptorConcentration[ii];
                    if (recconc > 0)
                    {
                        double[] recmit_L = Program.ReceptorConc[ii];
                        lock (recmit_L)
                        {
                            recmit_L[SG_nteil] += recconc;
                        }

                        if (recconc > Program.ReceptorParticleMaxConc[ii][SG_nteil])
                        {
                            Interlocked.Exchange(ref Program.ReceptorParticleMaxConc[ii][SG_nteil], recconc);
                        }
                    }
                }
            }

        return continued;
    }
    public static bool Guard_4(double xcoord_nteil, double ycoord_nteil, float zcoord_nteil, double masse, float idt, double mass_real)
    {
        bool continued = false;
        int SG_nteil = 0;
        double[] ReceptorConcentration = { 0, .25, 1.5 };
        double epsilonW_Masse = masse;
        if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, masse, idt))
                {
                    goto REMOVE_PARTICLE;
                }
        continued = true;
    REMOVE_PARTICLE:
            // Add local receptor concentrations to receptor array and store maximum concentration part for each receptor
            if (Program.ReceptorsAvailable)
            {
                for (int ii = 1; ii < ReceptorConcentration.Length; ii++)
                {
                    double recconc = ReceptorConcentration[ii];
                    if (recconc > 0)
                    {
                        double[] recmit_L = Program.ReceptorConc[ii];
                        lock (recmit_L)
                        {
                            recmit_L[SG_nteil] += recconc;
                        }

                        if (recconc > Program.ReceptorParticleMaxConc[ii][SG_nteil])
                        {
                            Interlocked.Exchange(ref Program.ReceptorParticleMaxConc[ii][SG_nteil], recconc);
                        }
                    }
                }
            }

        return continued;
    }
    public static bool Guard_5(double xcoord_nteil, double ycoord_nteil, float zcoord_nteil, double masse, float idt, double mass_real)
    {
        bool continued = false;
        int SG_nteil = 0;
        double[] ReceptorConcentration = { 0, .25, 1.5 };
        double epsilonW_Masse = masse;
        if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, masse, idt))
                    {
                        goto REMOVE_PARTICLE;
                    }
        continued = true;
    REMOVE_PARTICLE:
            // Add local receptor concentrations to receptor array and store maximum concentration part for each receptor
            if (Program.ReceptorsAvailable)
            {
                for (int ii = 1; ii < ReceptorConcentration.Length; ii++)
                {
                    double recconc = ReceptorConcentration[ii];
                    if (recconc > 0)
                    {
                        double[] recmit_L = Program.ReceptorConc[ii];
                        lock (recmit_L)
                        {
                            recmit_L[SG_nteil] += recconc;
                        }

                        if (recconc > Program.ReceptorParticleMaxConc[ii][SG_nteil])
                        {
                            Interlocked.Exchange(ref Program.ReceptorParticleMaxConc[ii][SG_nteil], recconc);
                        }
                    }
                }
            }

        return continued;
    }
    public static bool Guard_6(double xcoord_nteil, double ycoord_nteil, float zcoord_nteil, double masse, float idt, double mass_real)
    {
        bool continued = false;
        int SG_nteil = 0;
        double[] ReceptorConcentration = { 0, .25, 1.5 };
        double epsilonW_Masse = masse;
        if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, masse, idt))
                    {
                        goto REMOVE_PARTICLE;
                    }
        continued = true;
    REMOVE_PARTICLE:
            // Add local receptor concentrations to receptor array and store maximum concentration part for each receptor
            if (Program.ReceptorsAvailable)
            {
                for (int ii = 1; ii < ReceptorConcentration.Length; ii++)
                {
                    double recconc = ReceptorConcentration[ii];
                    if (recconc > 0)
                    {
                        double[] recmit_L = Program.ReceptorConc[ii];
                        lock (recmit_L)
                        {
                            recmit_L[SG_nteil] += recconc;
                        }

                        if (recconc > Program.ReceptorParticleMaxConc[ii][SG_nteil])
                        {
                            Interlocked.Exchange(ref Program.ReceptorParticleMaxConc[ii][SG_nteil], recconc);
                        }
                    }
                }
            }

        return continued;
    }
    public static bool Guard_7(double xcoord_nteil, double ycoord_nteil, float zcoord_nteil, double masse, float idt, double mass_real)
    {
        bool continued = false;
        int SG_nteil = 0;
        double[] ReceptorConcentration = { 0, .25, 1.5 };
        double epsilonW_Masse = masse;
        if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, masse, idt))
                    {
                        goto REMOVE_PARTICLE;
                    }
        continued = true;
    REMOVE_PARTICLE:
            // Add local receptor concentrations to receptor array and store maximum concentration part for each receptor
            if (Program.ReceptorsAvailable)
            {
                for (int ii = 1; ii < ReceptorConcentration.Length; ii++)
                {
                    double recconc = ReceptorConcentration[ii];
                    if (recconc > 0)
                    {
                        double[] recmit_L = Program.ReceptorConc[ii];
                        lock (recmit_L)
                        {
                            recmit_L[SG_nteil] += recconc;
                        }

                        if (recconc > Program.ReceptorParticleMaxConc[ii][SG_nteil])
                        {
                            Interlocked.Exchange(ref Program.ReceptorParticleMaxConc[ii][SG_nteil], recconc);
                        }
                    }
                }
            }

        return continued;
    }
    public static bool Guard_8(double xcoord_nteil, double ycoord_nteil, float zcoord_nteil, double masse, float idt, double mass_real)
    {
        bool continued = false;
        int SG_nteil = 0;
        double[] ReceptorConcentration = { 0, .25, 1.5 };
        double epsilonW_Masse = masse;
        if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, masse, idt))
                {
                    goto REMOVE_PARTICLE;
                }
        continued = true;
    REMOVE_PARTICLE:
            // Add local receptor concentrations to receptor array and store maximum concentration part for each receptor
            if (Program.ReceptorsAvailable)
            {
                for (int ii = 1; ii < ReceptorConcentration.Length; ii++)
                {
                    double recconc = ReceptorConcentration[ii];
                    if (recconc > 0)
                    {
                        double[] recmit_L = Program.ReceptorConc[ii];
                        lock (recmit_L)
                        {
                            recmit_L[SG_nteil] += recconc;
                        }

                        if (recconc > Program.ReceptorParticleMaxConc[ii][SG_nteil])
                        {
                            Interlocked.Exchange(ref Program.ReceptorParticleMaxConc[ii][SG_nteil], recconc);
                        }
                    }
                }
            }

        return continued;
    }
    public static bool Guard_9(double xcoord_nteil, double ycoord_nteil, float zcoord_nteil, double masse, float idt, double mass_real)
    {
        bool continued = false;
        int SG_nteil = 0;
        double[] ReceptorConcentration = { 0, .25, 1.5 };
        double epsilonW_Masse = masse;
        if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, masse, idt))
                {
                    goto REMOVE_PARTICLE;
                }
        continued = true;
    REMOVE_PARTICLE:
            // Add local receptor concentrations to receptor array and store maximum concentration part for each receptor
            if (Program.ReceptorsAvailable)
            {
                for (int ii = 1; ii < ReceptorConcentration.Length; ii++)
                {
                    double recconc = ReceptorConcentration[ii];
                    if (recconc > 0)
                    {
                        double[] recmit_L = Program.ReceptorConc[ii];
                        lock (recmit_L)
                        {
                            recmit_L[SG_nteil] += recconc;
                        }

                        if (recconc > Program.ReceptorParticleMaxConc[ii][SG_nteil])
                        {
                            Interlocked.Exchange(ref Program.ReceptorParticleMaxConc[ii][SG_nteil], recconc);
                        }
                    }
                }
            }

        return continued;
    }
    public static bool Guard_10(double xcoord_nteil, double ycoord_nteil, float zcoord_nteil, double masse, float idt, double mass_real)
    {
        bool continued = false;
        int SG_nteil = 0;
        double[] ReceptorConcentration = { 0, .25, 1.5 };
        double epsilonW_Masse = masse;
        if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, epsilonW_Masse, idt))
                    {
                        goto REMOVE_PARTICLE;
                    }
        continued = true;
    REMOVE_PARTICLE:
            // Add local receptor concentrations to receptor array and store maximum concentration part for each receptor
            if (Program.ReceptorsAvailable)
            {
                for (int ii = 1; ii < ReceptorConcentration.Length; ii++)
                {
                    double recconc = ReceptorConcentration[ii];
                    if (recconc > 0)
                    {
                        double[] recmit_L = Program.ReceptorConc[ii];
                        lock (recmit_L)
                        {
                            recmit_L[SG_nteil] += recconc;
                        }

                        if (recconc > Program.ReceptorParticleMaxConc[ii][SG_nteil])
                        {
                            Interlocked.Exchange(ref Program.ReceptorParticleMaxConc[ii][SG_nteil], recconc);
                        }
                    }
                }
            }

        return continued;
    }
    public static bool Guard_11(double xcoord_nteil, double ycoord_nteil, float zcoord_nteil, double masse, float idt, double mass_real)
    {
        bool continued = false;
        int SG_nteil = 0;
        double[] ReceptorConcentration = { 0, .25, 1.5 };
        double epsilonW_Masse = masse;
        if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, masse, 0.1F) ||
                !Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, mass_real, 0.1F))
            {
                goto REMOVE_PARTICLE;
            }
        continued = true;
    REMOVE_PARTICLE:
            // Add local receptor concentrations to receptor array and store maximum concentration part for each receptor
            if (Program.ReceptorsAvailable)
            {
                for (int ii = 1; ii < ReceptorConcentration.Length; ii++)
                {
                    double recconc = ReceptorConcentration[ii];
                    if (recconc > 0)
                    {
                        double[] recmit_L = Program.ReceptorConc[ii];
                        lock (recmit_L)
                        {
                            recmit_L[SG_nteil] += recconc;
                        }

                        if (recconc > Program.ReceptorParticleMaxConc[ii][SG_nteil])
                        {
                            Interlocked.Exchange(ref Program.ReceptorParticleMaxConc[ii][SG_nteil], recconc);
                        }
                    }
                }
            }

        return continued;
    }
    public static bool Guard_12(double xcoord_nteil, double ycoord_nteil, float zcoord_nteil, double masse, float idt, double mass_real)
    {
        bool continued = false;
        int SG_nteil = 0;
        double[] ReceptorConcentration = { 0, .25, 1.5 };
        double epsilonW_Masse = masse;
        if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, masse, idt))
                {
                    goto REMOVE_PARTICLE;
                }
        continued = true;
    REMOVE_PARTICLE:
            // Add local receptor concentrations to receptor array and store maximum concentration part for each receptor
            if (Program.ReceptorsAvailable)
            {
                for (int ii = 1; ii < ReceptorConcentration.Length; ii++)
                {
                    double recconc = ReceptorConcentration[ii];
                    if (recconc > 0)
                    {
                        double[] recmit_L = Program.ReceptorConc[ii];
                        lock (recmit_L)
                        {
                            recmit_L[SG_nteil] += recconc;
                        }

                        if (recconc > Program.ReceptorParticleMaxConc[ii][SG_nteil])
                        {
                            Interlocked.Exchange(ref Program.ReceptorParticleMaxConc[ii][SG_nteil], recconc);
                        }
                    }
                }
            }

        return continued;
    }
    public static bool Guard_13(double xcoord_nteil, double ycoord_nteil, float zcoord_nteil, double masse, float idt, double mass_real)
    {
        bool continued = false;
        int SG_nteil = 0;
        double[] ReceptorConcentration = { 0, .25, 1.5 };
        double epsilonW_Masse = masse;
        if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, masse, idt))
                {
                    goto REMOVE_PARTICLE;
                }
        continued = true;
    REMOVE_PARTICLE:
            // Add local receptor concentrations to receptor array and store maximum concentration part for each receptor
            if (Program.ReceptorsAvailable)
            {
                for (int ii = 1; ii < ReceptorConcentration.Length; ii++)
                {
                    double recconc = ReceptorConcentration[ii];
                    if (recconc > 0)
                    {
                        double[] recmit_L = Program.ReceptorConc[ii];
                        lock (recmit_L)
                        {
                            recmit_L[SG_nteil] += recconc;
                        }

                        if (recconc > Program.ReceptorParticleMaxConc[ii][SG_nteil])
                        {
                            Interlocked.Exchange(ref Program.ReceptorParticleMaxConc[ii][SG_nteil], recconc);
                        }
                    }
                }
            }

        return continued;
    }
    public static bool Guard_14(double xcoord_nteil, double ycoord_nteil, float zcoord_nteil, double masse, float idt, double mass_real)
    {
        bool continued = false;
        int SG_nteil = 0;
        double[] ReceptorConcentration = { 0, .25, 1.5 };
        double epsilonW_Masse = masse;
        if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, masse, idt))
                    {
                        goto REMOVE_PARTICLE;
                    }
        continued = true;
    REMOVE_PARTICLE:
            // Add local receptor concentrations to receptor array and store maximum concentration part for each receptor
            if (Program.ReceptorsAvailable)
            {
                for (int ii = 1; ii < ReceptorConcentration.Length; ii++)
                {
                    double recconc = ReceptorConcentration[ii];
                    if (recconc > 0)
                    {
                        double[] recmit_L = Program.ReceptorConc[ii];
                        lock (recmit_L)
                        {
                            recmit_L[SG_nteil] += recconc;
                        }

                        if (recconc > Program.ReceptorParticleMaxConc[ii][SG_nteil])
                        {
                            Interlocked.Exchange(ref Program.ReceptorParticleMaxConc[ii][SG_nteil], recconc);
                        }
                    }
                }
            }

        return continued;
    }
    public static bool Guard_15(double xcoord_nteil, double ycoord_nteil, float zcoord_nteil, double masse, float idt, double mass_real)
    {
        bool continued = false;
        int SG_nteil = 0;
        double[] ReceptorConcentration = { 0, .25, 1.5 };
        double epsilonW_Masse = masse;
        if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, masse, idt))
                {
                    goto REMOVE_PARTICLE;
                }
        continued = true;
    REMOVE_PARTICLE:
            // Add local receptor concentrations to receptor array and store maximum concentration part for each receptor
            if (Program.ReceptorsAvailable)
            {
                for (int ii = 1; ii < ReceptorConcentration.Length; ii++)
                {
                    double recconc = ReceptorConcentration[ii];
                    if (recconc > 0)
                    {
                        double[] recmit_L = Program.ReceptorConc[ii];
                        lock (recmit_L)
                        {
                            recmit_L[SG_nteil] += recconc;
                        }

                        if (recconc > Program.ReceptorParticleMaxConc[ii][SG_nteil])
                        {
                            Interlocked.Exchange(ref Program.ReceptorParticleMaxConc[ii][SG_nteil], recconc);
                        }
                    }
                }
            }

        return continued;
    }
    public static bool Guard_16(double xcoord_nteil, double ycoord_nteil, float zcoord_nteil, double masse, float idt, double mass_real)
    {
        bool continued = false;
        int SG_nteil = 0;
        double[] ReceptorConcentration = { 0, .25, 1.5 };
        double epsilonW_Masse = masse;
        if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, masse, idt))
                {
                    goto REMOVE_PARTICLE;
                }
        continued = true;
    REMOVE_PARTICLE:
            // Add local receptor concentrations to receptor array and store maximum concentration part for each receptor
            if (Program.ReceptorsAvailable)
            {
                for (int ii = 1; ii < ReceptorConcentration.Length; ii++)
                {
                    double recconc = ReceptorConcentration[ii];
                    if (recconc > 0)
                    {
                        double[] recmit_L = Program.ReceptorConc[ii];
                        lock (recmit_L)
                        {
                            recmit_L[SG_nteil] += recconc;
                        }

                        if (recconc > Program.ReceptorParticleMaxConc[ii][SG_nteil])
                        {
                            Interlocked.Exchange(ref Program.ReceptorParticleMaxConc[ii][SG_nteil], recconc);
                        }
                    }
                }
            }

        return continued;
    }
    public static bool Guard_17(double xcoord_nteil, double ycoord_nteil, float zcoord_nteil, double masse, float idt, double mass_real)
    {
        bool continued = false;
        int SG_nteil = 0;
        double[] ReceptorConcentration = { 0, .25, 1.5 };
        double epsilonW_Masse = masse;
        if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, epsilonW_Masse, idt))
                    {
                        goto REMOVE_PARTICLE;
                    }
        continued = true;
    REMOVE_PARTICLE:
            // Add local receptor concentrations to receptor array and store maximum concentration part for each receptor
            if (Program.ReceptorsAvailable)
            {
                for (int ii = 1; ii < ReceptorConcentration.Length; ii++)
                {
                    double recconc = ReceptorConcentration[ii];
                    if (recconc > 0)
                    {
                        double[] recmit_L = Program.ReceptorConc[ii];
                        lock (recmit_L)
                        {
                            recmit_L[SG_nteil] += recconc;
                        }

                        if (recconc > Program.ReceptorParticleMaxConc[ii][SG_nteil])
                        {
                            Interlocked.Exchange(ref Program.ReceptorParticleMaxConc[ii][SG_nteil], recconc);
                        }
                    }
                }
            }

        return continued;
    }
    public static bool HasTimeStepGuard(int i) => new bool[]{false,false,true,true,true,true,true,true,true,true,true,false,true,true,true,true,true,true}[i];
}
