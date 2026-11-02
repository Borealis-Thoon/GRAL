// Generated trajectory body retains GRAL GPL-3.0 source provenance. This support layer is task local.
template<class T,int N> struct Arr {
 T* p; int d[N];
 __device__ Arr<T,N-1> operator[](int i) const { Arr<T,N-1> a; int stride=1; for(int j=1;j<N;j++){a.d[j-1]=d[j];stride*=d[j];} a.p=p+i*stride;return a; }
 __device__ int size()const{return d[0];}
 __device__ int upper(int k)const{return d[k]-1;}
 __device__ bool operator==(decltype(nullptr))const{return p==nullptr;}
 __device__ bool operator!=(decltype(nullptr))const{return p!=nullptr;}
 __device__ T& operator()(int i,int j)const{return p[i*d[1]+j];}
};
template<class T> struct Arr<T,1> {
 T* p; int d[1];
 __device__ T& operator[](int i) const{return p[i];}
 __device__ int size()const{return d[0];}
 __device__ int upper(int)const{return d[0]-1;}
 __device__ bool operator==(decltype(nullptr))const{return p==nullptr;}
 __device__ bool operator!=(decltype(nullptr))const{return p!=nullptr;}
 __device__ void clear(){for(int i=0;i<d[0];i++)p[i]=T{};}
};
struct TimeSeriesColumn {Arr<float,1> Value;};
struct TransientDeposition {double Vsed,Vdep;int DepositionMode;};
template<class A,class B>struct Tuple2{A v0;B v1;};
template<class A,class B,class C,class D>struct Tuple4{A v0;B v1;C v2;D v3;};
template<class T>__device__ T gral_abs(T x){return x<0?-x:x;}
template<>__device__ float gral_abs(float x){return fabsf(x);}
template<>__device__ double gral_abs(double x){return fabs(x);}
template<>__device__ int gral_abs(int x){if(x==(-2147483647-1))asm("trap;");return x<0?-x:x;}
template<class T>__device__ T gral_min(T a,T b){return a<b?a:b;}
template<class T>__device__ T gral_max(T a,T b){return a>b?a:b;}
template<>__device__ float gral_min(float a,float b){return isnan(a)?a:a==b?(signbit(a)?a:b):a<b?a:b;}
template<>__device__ double gral_min(double a,double b){return isnan(a)?a:a==b?(signbit(a)?a:b):a<b?a:b;}
template<>__device__ float gral_max(float a,float b){return isnan(a)?a:a==b?(signbit(a)?b:a):a>b?a:b;}
template<>__device__ double gral_max(double a,double b){return isnan(a)?a:a==b?(signbit(a)?b:a):a>b?a:b;}
template<class T>__device__ T gral_clamp(T a,T b,T c){return gral_min(gral_max(a,b),c);}
template<class T>__device__ int gral_sign(T a){return a<0?-1:a>0?1:0;}
template<>__device__ int gral_sign(float a){if(isnan(a))asm("trap;");return a<0?-1:a>0?1:0;}
template<>__device__ int gral_sign(double a){if(isnan(a))asm("trap;");return a<0?-1:a>0?1:0;}
// .NET 9+ saturating floating-point-to-integer conversions, including NaN -> zero.
template<class T>__device__ T cs_cast(double x);
template<>__device__ int cs_cast<int>(double x){if(isnan(x))return 0;if(x>=2147483647.0)return 2147483647;if(x<=-2147483648.0)return (-2147483647-1);return (int)x;}
template<>__device__ unsigned int cs_cast<unsigned int>(double x){if(isnan(x)||x<=0)return 0;if(x>=4294967295.0)return 4294967295u;return (unsigned int)x;}
template<>__device__ long long cs_cast<long long>(double x){if(isnan(x))return 0;if(x>=9223372036854775808.0)return 9223372036854775807ll;if(x<=-9223372036854775808.0)return (-9223372036854775807ll-1);return (long long)x;}
template<>__device__ unsigned long long cs_cast<unsigned long long>(double x){if(isnan(x)||x<=0)return 0;if(x>=18446744073709551616.0)return 18446744073709551615ull;return (unsigned long long)x;}
__device__ float gral_round(float x,int digits){float z=powf(10.0f,digits);return nearbyintf(x*z)/z;}
template<class T,class V>__device__ T atomic_add(T* p,V v){return atomicAdd(p,(T)v);}
template<class V>__device__ long long atomic_add(long long* p,V v){return (long long)atomicAdd((unsigned long long*)p,(unsigned long long)v);}
template<class T>__device__ T atomic_inc(T* p){return atomic_add(p,1)+1;}
__device__ double atomic_exchange(double* p,double v){return __longlong_as_double((long long)atomicExch((unsigned long long*)p,(unsigned long long)__double_as_longlong(v)));}
__device__ int atomic_compare(int* p,int cmp,int val){return atomicCAS(p,cmp,val);}
