using System;
using Program = ExpiryProbeProgram;
using Consts = ExpiryFixtureConstants;
using TransientConcentration = ExpiryStorageFixture;
static class ExpiryProbeProgram { public static bool ParticleStateIsFinite(double x,double y,float z,double mass,float dt) => ExitProbeProgram.Check(x,y,z,mass,dt); }
static class ExpiryFixtureConstants { public const int DepoOff=0, TransientMode=0, SourceTypePoint=0, SourceTypePortal=1, ParticleIsNotAPortal=1; }
static class ExpiryStorageFixture { public static int Calls; public static Action<int,float,float,double,double,float,double,double,int> Save; public static void Conz5dZeitschleife(int r,float z,float h,double m,double a,float dt,double x,double y,int sg) { Calls++;Save(r,z,h,m,a,dt,x,y,sg); } }
static class ExtractedTransientExpiry
{
    public static bool warning_free_baseline(int SourceType,float zcoord_nteil,float vsed,float idt,bool expired,double masse=1)
    {
        double xcoord_nteil=25,ycoord_nteil=25,xsi=25,eta=25,Area_cart=400;
        _ = (xcoord_nteil, ycoord_nteil);
        float auszeit=0,tgesamt=expired?.05f:100,wpHurley=0,AHint=0;
        int Deposition_type=1,ISTATIONAER=0,tunfak=1,reflexion_flag=0,SG_nteil=0;
                if (Deposition_type > Consts.DepoOff && vsed > 0) // compute sedimentation for this particle
                {
                    zcoord_nteil -= vsed * idt;
                }

                //control dispersion time of particles
                auszeit += idt;
                if (ISTATIONAER == Consts.TransientMode)
                {
                    if (auszeit >= tgesamt)
                    {
                        //particles from point sources with exit velocities are tracked until this velocity becomes almost zero
                        if (SourceType == Consts.SourceTypePoint)
                        {
                            if (wpHurley < 0.01)
                            {
                                TransientConcentration.Conz5dZeitschleife(reflexion_flag, zcoord_nteil, AHint, masse, Area_cart, idt, xsi, eta, SG_nteil);
                                goto REMOVE_PARTICLE;
                            }
                        }
                        //particles from portal sources with exit velocities are tracked until this velocity became zero
                        else if (SourceType == Consts.SourceTypePortal)
                        {
                            if (tunfak == Consts.ParticleIsNotAPortal)
                            {
                                TransientConcentration.Conz5dZeitschleife(reflexion_flag, zcoord_nteil, AHint, masse, Area_cart, idt, xsi, eta, SG_nteil);
                                goto REMOVE_PARTICLE;
                            }
                        }
                        else
                        {
                            TransientConcentration.Conz5dZeitschleife(reflexion_flag, zcoord_nteil, AHint, masse, Area_cart, idt, xsi, eta, SG_nteil);
                            goto REMOVE_PARTICLE;
                        }
                    }
                }


        return true;
    REMOVE_PARTICLE:
        return false;
    }
    public static bool nan_guard_state(int SourceType,float zcoord_nteil,float vsed,float idt,bool expired,double masse=1)
    {
        double xcoord_nteil=25,ycoord_nteil=25,xsi=25,eta=25,Area_cart=400;
        _ = (xcoord_nteil, ycoord_nteil);
        float auszeit=0,tgesamt=expired?.05f:100,wpHurley=0,AHint=0;
        int Deposition_type=1,ISTATIONAER=0,tunfak=1,reflexion_flag=0,SG_nteil=0;
                if (Deposition_type > Consts.DepoOff && vsed > 0) // compute sedimentation for this particle
                {
                    zcoord_nteil -= vsed * idt;
                }

                if (!Program.ParticleStateIsFinite(xcoord_nteil, ycoord_nteil, zcoord_nteil, masse, idt))
                {
                    goto REMOVE_PARTICLE;
                }

                //control dispersion time of particles
                auszeit += idt;
                if (ISTATIONAER == Consts.TransientMode)
                {
                    if (auszeit >= tgesamt)
                    {
                        //particles from point sources with exit velocities are tracked until this velocity becomes almost zero
                        if (SourceType == Consts.SourceTypePoint)
                        {
                            if (wpHurley < 0.01)
                            {
                                TransientConcentration.Conz5dZeitschleife(reflexion_flag, zcoord_nteil, AHint, masse, Area_cart, idt, xsi, eta, SG_nteil);
                                goto REMOVE_PARTICLE;
                            }
                        }
                        //particles from portal sources with exit velocities are tracked until this velocity became zero
                        else if (SourceType == Consts.SourceTypePortal)
                        {
                            if (tunfak == Consts.ParticleIsNotAPortal)
                            {
                                TransientConcentration.Conz5dZeitschleife(reflexion_flag, zcoord_nteil, AHint, masse, Area_cart, idt, xsi, eta, SG_nteil);
                                goto REMOVE_PARTICLE;
                            }
                        }
                        else
                        {
                            TransientConcentration.Conz5dZeitschleife(reflexion_flag, zcoord_nteil, AHint, masse, Area_cart, idt, xsi, eta, SG_nteil);
                            goto REMOVE_PARTICLE;
                        }
                    }
                }


        return true;
    REMOVE_PARTICLE:
        return false;
    }
}
