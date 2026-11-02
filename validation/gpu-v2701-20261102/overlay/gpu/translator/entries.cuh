extern "C" __global__ void gral_fresh(int first,int count){int q=blockIdx.x*blockDim.x+threadIdx.x;if(q<count){Zeitschleife_Calculate(first+q);}}
extern "C" __global__ void gral_residual(int count,int trace_base,const int* i,const int* j,const int* k,const int* sg,const float* conc,const int* split){int q=blockIdx.x*blockDim.x+threadIdx.x;if(q<count)ZeitschleifeNonSteadyState_ParticleDriver(i[q],j[q],k[q],sg[q],conc[q],split[q],trace_base+q);}
extern "C" __global__ void gral_state_size(unsigned long long* result){*result=sizeof(State);}
