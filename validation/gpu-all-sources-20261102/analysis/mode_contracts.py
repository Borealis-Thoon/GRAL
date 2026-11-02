import math

"""Mode-aware GPU counters for the fixed four-source synthetic fixtures."""
COHORTS=('transient_all_sources','steady_all_sources')


def validate_gpu_phase_counts(rows,cohort,hours):
    if cohort not in COHORTS or [r['situation'] for r in rows]!=list(range(1,hours+1)):
        raise ValueError('Mode or GPU situation sequence mismatch.')
    previous={'fresh':0,'residual':0}
    previous_launches=0
    previous_device_ms=0.0
    totals={'fresh_total':0,'residual_total':0,'mode':cohort,'situations':hours,'phase_counter_scope':'host completed GPU request counts, not in-kernel counters'}
    for row in rows:
        fresh=row['fresh_particles'];residual=row['residual_particles'];batches=row['residual_batches']
        if any(type(v) is not int or v<0 for v in (fresh,residual,batches)) or fresh<=0:
            raise ValueError('Invalid dispatched GPU particle count.')
        active=row['fresh_active_particles']
        if type(active) is not int or not 0<active<=fresh:raise ValueError('No active fresh source particles.')
        phases=row['phase_counts']
        launches=row.get('result_server_metrics',{}).get('kernel_launches')
        if type(launches) is not int or launches<=previous_launches:raise ValueError('No actual kernel launch in a measured situation.')
        previous_launches=launches
        device_ms=row.get('result_server_metrics',{}).get('kernel_device_ms')
        if not isinstance(device_ms,(int,float)) or not math.isfinite(device_ms) or device_ms<=previous_device_ms:raise ValueError('No positive CUDA-event work in a measured situation.')
        previous_device_ms=device_ms
        if any(type(phases.get(k)) is not int or phases[k]-previous[k]!=value for k,value in (('fresh',fresh),('residual',residual))):
            raise ValueError('Completed GPU request count differs from dispatched particle count.')
        if (residual==0)!=(batches==0):raise ValueError('Residual particle/batch count mismatch.')
        if cohort=='steady_all_sources' and (residual or batches or phases['residual']):
            raise ValueError('Steady execution performed transient residual work.')
        totals['fresh_total']+=fresh;totals['residual_total']+=residual
        previous=dict(phases)
    if cohort=='transient_all_sources' and hours>1 and totals['residual_total']==0:
        raise ValueError('Transient primary fixture did not exercise residual carryover.')
    return totals
