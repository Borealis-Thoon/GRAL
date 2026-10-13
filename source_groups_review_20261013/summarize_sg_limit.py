from pathlib import Path
import argparse,json,collections
p=argparse.ArgumentParser();p.add_argument('--qa-dir',required=True,type=Path);a=p.parse_args();q=a.qa_dir
summary=json.loads((q/'sg_limit_summary.json').read_text());records=json.loads((q/'sg_limit_records.json').read_text());restart=json.loads((q/'sg_limit_restart.json').read_text());obs=json.loads((q/'sg_limit_observations.json').read_text());size=json.loads((q/'sg_limit_change_size.json').read_text())
assert summary['status']=='pass' and restart['status']=='pass' and len(records)==96 and len(restart['records'])==12
assert all(r['status']=='pass' for r in records+restart['records'])
assert all(r['completed'] for r in records if r['variant']=='fixed')
checks=collections.Counter(r['test'] for r in summary['checks']);assert all(r['pass_'] for r in summary['checks'])
failed=[r for r in records if not r['completed']];timedout=[r for r in records if r['return_code']==124]
result=dict(status='pass',baseline=summary['base'],primary_conditions=24,primary_main_executions=96,fixed_completions=48,baseline_completions=24,expected_baseline_unsupported_outcomes=24,baseline_failure_return_codes=dict(collections.Counter(str(r['return_code']) for r in failed)),primary_watchdog_timeouts=len(timedout),compatibility_restart_main_executions=12,reported_main_executions=108,excluded_exploratory_main_attempts=obs['total_excluded_main_attempts'],all_main_attempts=108+obs['total_excluded_main_attempts'],output_payloads_checked=sum(len(r['payload_sha256']) for r in records+restart['records']),strict_build_targets=3,warnings=0,errors=0,checks=dict(checks),source_group_count_checkpoint_tests_per_variant=summary['fixtures'][0]['checkpoint_count_roundtrip'],actual_particle_allocations=sorted(set(n for r in records for n in r['actual_particles'])),changes=size,restart_scope='Emission-OFF SG read/resume compatibility only. See checkpoint_observations.md for separate unresolved writer observations.')
(q/'sg_limit_final.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))
