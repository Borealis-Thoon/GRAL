"""PNG diagnostics for observed GRAL runs; labels keep measurement scope explicit."""
from __future__ import annotations
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

COLORS={'cpu':'#28587B','gpu':'#D55E00'}
GROUP_LABELS={'1':'AREA','2':'Horizontal LINE','3':'POINT','4':'PORTAL','aggregate':'Aggregate'}
PHASES=['init_roundtrip_s','residual_split_s','residual_roundtrip_s','fresh_roundtrip_s','result_request_to_header_s','result_transfer_apply_s']


def save(fig,path):
    fig.tight_layout(rect=(0,0,1,.96))
    fig.savefig(path,dpi=180,bbox_inches='tight')
    plt.close(fig)


def timing_figures(runs,out:Path):
    timing=[r for r in runs if r['seed_offset']==0]
    fig,axes=plt.subplots(1,2,figsize=(13,4.4),sharey=True)
    for ax,hours in zip(axes,(24,48)):
        for backend in ('cpu','gpu'):
            chosen=[r for r in timing if r['hours']==hours and r['backend']==backend]
            matrix=[]
            for r in chosen:
                y=[s['wall_s'] for s in r['series']]
                matrix.append(y)
                ax.plot(np.arange(1,hours+1),y,color=COLORS[backend],alpha=.25,linewidth=.8)
            if matrix:
                ax.plot(np.arange(1,hours+1),np.median(matrix,axis=0),color=COLORS[backend],label=f'{backend.upper()} median (n={len(matrix)})')
        ax.axvspan(.5,3.5,color='#dddddd',alpha=.5,label='First 3 excluded from steady timing')
        ax.set(title=f'{hours} situations',xlabel='Situation',ylabel='Full situation observer interval (s)')
        ax.grid(alpha=.15); ax.legend(fontsize=7)
    fig.suptitle('Fixed-seed repeats; faint lines are individual runs')
    save(fig,out/'situation_time_repeats.png')
    fig,axes=plt.subplots(1,2,figsize=(12,4.3))
    for ax,key,title in zip(axes,('process_start_to_exit_s','steady_boundary_wall_s'),('Process start to exit','Boundary start after situation 3 to stop / drain')):
        positions=[]
        labels=[]
        for pos,(hours,backend) in enumerate((h,b) for h in (24,48) for b in ('cpu','gpu')):
            vals=[r[key] for r in timing if r['hours']==hours and r['backend']==backend]
            ax.scatter(np.full(len(vals),pos)+np.linspace(-.06,.06,len(vals)),vals,color=COLORS[backend],s=40)
            if vals: ax.hlines(np.median(vals),pos-.2,pos+.2,color='black',linewidth=1.5)
            positions.append(pos); labels.append(f'{hours} situations {backend.upper()}')
        ax.set_xticks(positions,labels);ax.set(title=title,ylabel='Wall time (s)');ax.grid(axis='y',alpha=.15)
    fig.suptitle('Three fixed-seed repetitions per backend and duration; bars are medians')
    save(fig,out/'timing_variability.png')


def memory_figures(runs,out:Path):
    for hours in (24,48):
        selected=[]
        for backend in ('cpu','gpu'):
            matches=[r for r in runs if r['hours']==hours and r['backend']==backend and r['seed_offset']==0]
            if matches: selected.append(matches[0])
        fig,axes=plt.subplots(3,2,figsize=(14,9),squeeze=False,sharey='row')
        for col,r in enumerate(selected):
            detail=defaultdict(list)
            for row in r['memory_detail']:
                detail[(row['pid'],row['name'])].append(row)
            for (pid,name),rows in detail.items():
                runtime='C# / dotnet' if name.lower().startswith('dotnet') else 'Python' if name.lower().startswith('python') else name
                color='#28587B' if runtime=='C# / dotnet' else '#D55E00' if runtime=='Python' else '#777777'
                linestyle='-' if runtime in ('C# / dotnet','Python') else '--'
                for j,key in enumerate(('rss_bytes','private_bytes')):
                    points=[(float(x['elapsed_s']),float(x[key])/2**20) for x in rows if x.get(key) is not None]
                    if points:
                        t,y=zip(*points);axes[j,col].plot(t,y,label=f'{runtime} PID {pid}',color=color,linestyle=linestyle,linewidth=1)
            rows=r['gpu_telemetry']
            points=[(float(x['elapsed_s']),float(x['device_memory_used_mib'])) for x in rows if x.get('device_memory_used_mib') not in ('',None) and not x.get('query_error')]
            if points:
                t,y=zip(*points);axes[2,col].plot(t,y,color='#009E73',label='Device-wide used VRAM')
            for j,label in enumerate(('Process RSS (MiB)','Process private (MiB)','Device-wide GPU memory (MiB)')):
                axes[j,col].set(xlabel='Telemetry elapsed time (s)',ylabel=label)
                axes[j,col].grid(alpha=.15)
                if axes[j,col].lines:axes[j,col].legend(fontsize=7)
                else: axes[j,col].text(.5,.5,'Measurement unavailable',ha='center',transform=axes[j,col].transAxes)
            axes[0,col].set_title(f'{r["backend"].upper()} {hours} situations / {r["run_id"]}')
        fig.suptitle('Representative base-seed run; sampled values; GPU total is not process VRAM')
        save(fig,out/f'memory_walltime_{hours}h.png')
        fig,axes=plt.subplots(1,2,figsize=(13,4))
        for backend in ('cpu','gpu'):
            repeats=[r for r in runs if r['hours']==hours and r['backend']==backend and r['seed_offset']==0]
            for ax,key,label in ((axes[0],'peak_tree_rss_bytes','Tree RSS'),(axes[1],'peak_tree_private_bytes','Tree private')):
                values=[]
                for r in repeats:
                    x=[v['situation'] for v in r['series']]
                    y=[np.nan if v.get(key) is None else v[key]/2**20 for v in r['series']]
                    values.append(y)
                    ax.plot(x,y,color=COLORS[backend],alpha=.25,linewidth=.8)
                if values:ax.plot(x,np.median(values,axis=0),color=COLORS[backend],label=f'{backend.upper()} median (n={len(values)})')
                ax.set(xlabel='Situation',ylabel=f'Sampled peak {label} (MiB)')
                ax.grid(alpha=.15);ax.legend(fontsize=8)
        fig.suptitle(f'{hours} situations fixed-seed repeats; faint lines are individual runs')
        save(fig,out/f'memory_per_situation_{hours}h.png')


def science_figures(fields,summary,out:Path):
    groups=list(summary['groups'])
    fig,axes=plt.subplots(len(groups),3,figsize=(12,3.2*len(groups)),squeeze=False)
    for row,group in enumerate(groups):
        c=fields[('cpu',0)][group][3:].mean(axis=0)
        g=fields[('gpu',0)][group][3:].mean(axis=0)
        high=max(float(c.max()),float(g.max())); delta=g-c; bound=float(np.abs(delta).max())
        for col,arr in enumerate((c,g,delta)):
            kw=dict(cmap='viridis',vmin=0,vmax=high if high else 1) if col<2 else dict(cmap='RdBu_r',vmin=-bound if bound else -1,vmax=bound if bound else 1)
            m=axes[row,col].imshow(arr.T,origin='lower',**kw)
            axes[row,col].set(title=f'{GROUP_LABELS[group]} / {("CPU","GPU","GPU - CPU")[col]}',xlabel='Grid x index',ylabel='Grid y index')
            fig.colorbar(m,ax=axes[row,col],shrink=.8,label='Concentration (model output units)')
    fig.suptitle('Base seed: time mean over situations 4..24; shared CPU/GPU scale within each group')
    save(fig,out/'seed0_mean_spatial_maps.png')
    fig,axes=plt.subplots(3,2,figsize=(10,12))
    for ax,group in zip(axes.ravel(),groups):
        for offset in sorted(s for b,s in fields if b=='cpu'):
            c=fields[('cpu',offset)][group][3:].mean(axis=0).ravel()
            g=fields[('gpu',offset)][group][3:].mean(axis=0).ravel()
            ax.scatter(c,g,s=3,alpha=.12,rasterized=True,label=str(offset))
        high=max(ax.get_xlim()[1],ax.get_ylim()[1]);ax.plot([0,high],[0,high],color='black',linewidth=.7)
        ax.set(title=GROUP_LABELS[group],xlabel='CPU time-mean concentration',ylabel='GPU time-mean concentration',xlim=(0,high),ylim=(0,high))
    for ax in axes.ravel()[len(groups):]:ax.set_visible(False)
    fig.suptitle('Same-seed paired mean maps; all six offsets; cells are not independent replicates')
    save(fig,out/'seed_twins_scatter.png')
    fig,axes=plt.subplots(1,2,figsize=(13,5.3))
    for ax,key in zip(axes,('R','V')):
        for index,group in enumerate(groups):
            values=[b[key] for b in summary['groups'][group]['blocks']]
            for j,value in enumerate(values):
                if value is not None and np.isfinite(value):ax.scatter(value,index+(j-1)*.13,s=40,color=('#28587B','#D55E00','#009E73')[j],marker=('o','s','^')[j],label=f'Block {j+1}' if index==0 else None)
                else:ax.text(.98,index+(j-1)*.13,'undefined' if value is None else 'infinite',ha='right',transform=ax.get_yaxis_transform())
            boot=summary['groups'][group]['bootstrap'][key]
            if boot['p2_5'] is not None:
                ax.hlines(index-.28,boot['p2_5'],boot['p97_5'],color='gray',linewidth=2)
        ax.axvline(1,color='black',linestyle='--',linewidth=1)
        if key=='V':ax.axvspan(.5,2,color='#eeeeee',zorder=0)
        ax.set_yticks(range(len(groups)),[GROUP_LABELS[g] for g in groups]);ax.set_xlabel('Error / CPU interseed variation' if key=='R' else 'GPU / CPU interseed variation')
        ax.set_title(f'{key}: three disjoint prespecified seed-pair blocks');ax.legend(fontsize=8);ax.grid(alpha=.15)
    fig.suptitle('Gray intervals: descriptive 27-resample bootstrap; no established 95% coverage')
    save(fig,out/'seed_R_V_blocks.png')


def seed_metric_figures(summary,out:Path):
    fig,axes=plt.subplots(2,2,figsize=(12,8))
    for color,(group,entry) in zip(('#28587B','#D55E00','#009E73','#CC79A7','#7A6612'),summary['groups'].items()):
        rows=entry['primary_seed_metrics'];seeds=[r['seed_offset'] for r in rows]
        metrics=[('weighted_nmae','Symmetric weighted NMAE'),('normalized_bias','Signed normalized bias'),('spatial_pearson','Spatial decorrelation (1 - Pearson r)'),('p99','P99 signed concentration difference')]
        for ax,(key,label) in zip(axes.ravel(),metrics):
            vals=[r[key]['difference'] if key=='p99' else (np.nan if r[key] is None else 1-r[key] if key=='spatial_pearson' else r[key]) for r in rows]
            ax.plot(seeds,vals,marker='o',markersize=4,color=color,label=GROUP_LABELS[group])
            ax.set(xlabel='Seed offset',ylabel=label);ax.grid(alpha=.15)
            if key=='spatial_pearson':ax.ticklabel_format(axis='y',style='sci',scilimits=(0,0),useOffset=False)
    axes[0,0].legend(fontsize=8)
    fig.suptitle('Six seed pairs; situations 4..24; raw per-seed metrics')
    save(fig,out/'seed_level_metrics.png')


def gpu_phase_figures(runs,out:Path):
    for hours in (24,48):
        selected=[r for r in runs if r['hours']==hours and r['backend']=='gpu' and r['seed_offset']==0]
        if not selected or not selected[0]['gpu_metrics']:continue
        r=selected[0];rows=r['gpu_metrics'];x=np.array([v['situation'] for v in rows]);base=np.zeros(len(rows))
        fig,axes=plt.subplots(3,1,figsize=(12,10))
        for phase in PHASES:
            y=np.array([v[phase] for v in rows]);axes[0].bar(x,y,bottom=base,label=phase.removesuffix('_s'));base+=y
        axes[0].set(ylabel='Host phase wall time (s)',title='Host phase breakdown; kernel time is nested and is not added');axes[0].legend(fontsize=7,ncol=3)
        kernel=np.array([np.nan if value is None else value for value in r['gpu_device_interval_ms']])/1000
        axes[1].plot(x,[v['result_transfer_apply_s'] for v in rows],label='Result receive + apply',color='#D55E00')
        axes[1].plot(x,kernel,label='CUDA-event kernel interval (nested; counter delta)',color='#28587B')
        axes[1].set(ylabel='Time (s)');axes[1].legend(fontsize=8)
        axes[2].plot(x,[v.get('saved_payload_bytes',0)/2**20 for v in rows],label='Omitted init payload MiB')
        axes[2].plot(x,[v.get('bytes_sent',0)/2**20 for v in rows],label='Actual sent MiB')
        axes[2].set(xlabel='Situation',ylabel='Payload (MiB)');axes[2].legend(fontsize=8)
        for ax in axes:ax.grid(alpha=.15)
        fig.suptitle(f'{hours} situations / {r["run_id"]}; init includes cache hashing; representative base seed')
        save(fig,out/f'gpu_pipeline_phases_{hours}h.png')
        fig,axes=plt.subplots(1,2,figsize=(12,4))
        for key in ('buffer_allocation_count','buffer_reuse_count','buffer_free_count'):
            values=[v.get('result_server_metrics',{}).get(key,np.nan) for v in rows]
            axes[0].plot(x,values,label=key.removesuffix('_count'))
        for key in ('device_buffer_bytes','peak_device_buffer_bytes'):
            values=[v.get('result_server_metrics',{}).get(key,np.nan)/2**20 for v in rows]
            axes[1].plot(x,values,label=key)
        axes[0].set(ylabel='Server cumulative count',xlabel='Situation')
        axes[1].set(ylabel='Application buffer allocations (MiB)',xlabel='Situation')
        for ax in axes:ax.grid(alpha=.15);ax.legend(fontsize=8)
        fig.suptitle(f'{hours} situations device buffer accounting; application counters are not measured VRAM')
        save(fig,out/f'gpu_buffer_reuse_{hours}h.png')


def render_all(runs,fields,summary,out):
    out.mkdir()
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
    timing_figures(runs,out);memory_figures(runs,out);science_figures(fields,summary,out);seed_metric_figures(summary,out);gpu_phase_figures(runs,out)
