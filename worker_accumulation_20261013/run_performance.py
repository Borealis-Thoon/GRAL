import sys
import run_main as m

def cases():
 rows=[]
 for name,workers,particles in [('concentrated_100k_w4',4,100000),('concentrated_100k_w24',24,100000),('concentrated_1m_w24',24,1000000)]:
  rows.append(dict(id=name,dx=40,budget=particles,kind='point',sources=2,groups=2,pattern='steady',workers=workers,ratio=1,duration=120,situations=1,wind_m_s=.25,stability=6,slices=1,mode='stationary',mb=256))
 rows.append(dict(id='dense_grid_100k_w24',dx=10,budget=100000,kind='area',sources=8,groups=8,pattern='steady',workers=24,ratio=1,duration=60,situations=1,wind_m_s=1,stability=4,slices=9,mode='stationary',mb=256,concentrated=False,length=1200,flow=40,conc=10))
 return rows
if __name__=='__main__':
 m.cases=cases
 if '--repeat' not in sys.argv:sys.argv.extend(['--repeat','5'])
 if '--run-name' not in sys.argv:sys.argv.extend(['--run-name','performance'])
 if '--max-seconds' not in sys.argv:sys.argv.extend(['--max-seconds','240'])
 m.main()