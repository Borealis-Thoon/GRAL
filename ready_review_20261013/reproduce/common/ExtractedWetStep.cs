using System;
using Program = WetProbeProgram;
static class ExtractedWetStep
{
    public static bool warning_free_baseline_new(double masse, float idt, double decay_rate, out double remainingMass)
    {
        double xcoord_nteil = 1, ycoord_nteil = 1;
        float zcoord_nteil = 1;
        _ = (xcoord_nteil, ycoord_nteil, zcoord_nteil);
        bool reachedWrite = false;
        if (WetProbeProgram.ForceExit) goto REMOVE_PARTICLE;
                //decay rate
                if (decay_rate > 0)
                {
                    masse *= Math.Exp(-decay_rate * idt);
                }

                // compute Wet deposition
                if (Program.WetDeposition == true && Program.WetDepoRW != 0)
                {
                    double epsilonW_Masse = masse * Program.WetDepoRW * idt; // deposited mass
                    bool ex = false;

                    if (epsilonW_Masse > masse)
                    {
                        epsilonW_Masse = masse;
                        ex = true;
                    }
                    masse -= epsilonW_Masse;
                    _ = ex;
                    reachedWrite = true;
                }
        remainingMass = masse;
        return reachedWrite;
    REMOVE_PARTICLE:
        remainingMass = masse;
        return false;
    }
    public static bool warning_free_baseline_residual(double masse, float idt, double decay_rate, out double remainingMass)
    {
        double xcoord_nteil = 1, ycoord_nteil = 1;
        float zcoord_nteil = 1;
        _ = (xcoord_nteil, ycoord_nteil, zcoord_nteil);
        bool reachedWrite = false;
        if (WetProbeProgram.ForceExit) goto REMOVE_PARTICLE;
                //decay rate
                if (decay_rate > 0)
                {
                    masse *= Math.Exp(-decay_rate * idt);
                }

                // compute Wet deposition
                if (Program.WetDeposition == true && Program.WetDepoRW != 0)
                {
                    double epsilonW_Masse = masse * Program.WetDepoRW * idt; // deposited mass
                    bool ex = false;

                    if (epsilonW_Masse > masse)
                    {
                        epsilonW_Masse = masse;
                        ex = true; // masse <= 0!
                    }

                    masse -= epsilonW_Masse;
                    _ = ex;
                    reachedWrite = true;
                }
        remainingMass = masse;
        return reachedWrite;
    REMOVE_PARTICLE:
        remainingMass = masse;
        return false;
    }
    public static bool nan_guard_state_new(double masse, float idt, double decay_rate, out double remainingMass)
    {
        double xcoord_nteil = 1, ycoord_nteil = 1;
        float zcoord_nteil = 1;
        _ = (xcoord_nteil, ycoord_nteil, zcoord_nteil);
        bool reachedWrite = false;
        if (WetProbeProgram.ForceExit) goto REMOVE_PARTICLE;
                //decay rate
                if (decay_rate > 0)
                {
                    masse *= Math.Exp(-decay_rate * idt);
                }

                if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, masse, idt))
                {
                    goto REMOVE_PARTICLE;
                }

                // compute Wet deposition
                if (Program.WetDeposition == true && Program.WetDepoRW != 0)
                {
                    double epsilonW_Masse = masse * Program.WetDepoRW * idt; // deposited mass
                    bool ex = false;

                    if (epsilonW_Masse > masse)
                    {
                        epsilonW_Masse = masse;
                        ex = true;
                    }
                    if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, epsilonW_Masse, idt))
                    {
                        goto REMOVE_PARTICLE;
                    }

                    masse -= epsilonW_Masse;
                    _ = ex;
                    reachedWrite = true;
                }
        remainingMass = masse;
        return reachedWrite;
    REMOVE_PARTICLE:
        remainingMass = masse;
        return false;
    }
    public static bool nan_guard_state_residual(double masse, float idt, double decay_rate, out double remainingMass)
    {
        double xcoord_nteil = 1, ycoord_nteil = 1;
        float zcoord_nteil = 1;
        _ = (xcoord_nteil, ycoord_nteil, zcoord_nteil);
        bool reachedWrite = false;
        if (WetProbeProgram.ForceExit) goto REMOVE_PARTICLE;
                //decay rate
                if (decay_rate > 0)
                {
                    masse *= Math.Exp(-decay_rate * idt);
                }

                if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, masse, idt))
                {
                    goto REMOVE_PARTICLE;
                }

                // compute Wet deposition
                if (Program.WetDeposition == true && Program.WetDepoRW != 0)
                {
                    double epsilonW_Masse = masse * Program.WetDepoRW * idt; // deposited mass
                    bool ex = false;

                    if (epsilonW_Masse > masse)
                    {
                        epsilonW_Masse = masse;
                        ex = true; // masse <= 0!
                    }

                    if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, epsilonW_Masse, idt))
                    {
                        goto REMOVE_PARTICLE;
                    }

                    masse -= epsilonW_Masse;
                    _ = ex;
                    reachedWrite = true;
                }
        remainingMass = masse;
        return reachedWrite;
    REMOVE_PARTICLE:
        remainingMass = masse;
        return false;
    }
}
