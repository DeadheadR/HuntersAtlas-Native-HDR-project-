"""Derive anonymous statistics from immutable native measurement sample files."""
from pathlib import Path
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from measure_session import distribution
from live_protocol import atomic_json,read_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);a=p.parse_args();s=a.session.resolve();report=read_json(s/'controlled-measurements.json')
    if not report.get('complete') or len(report['results'])!=36:raise RuntimeError('Completed known-scope series required')
    areas=[]
    for area in sorted(set(r['area'] for r in report['results'])):
        rows=[r for r in report['results'] if r['area']==area];entry=dict(area=area,warm={},cold={},closed={})
        for mode in ('static','reference'):
            warm=[r for r in rows if r['condition'].startswith(mode+'_warm')];present=[];cpu=[]
            for row in warm:
                raw=read_json(row['raw_samples']);present.extend(raw['present_interval_ms'][2:]);cpu.extend(raw['map_cpu_elapsed_ms'][2:])
            values=distribution(cpu);values.pop('fps_from_interval_mean',None)
            entry['warm'][mode]=dict(repetitions=len(warm),present=distribution(present),map_cpu=values,repeat_present_means_ms=[r['present']['mean_ms'] for r in warm],repeat_map_cpu_means_ms=[r['map_cpu']['mean_ms'] for r in warm])
            cold=next(r for r in rows if r['condition']==mode+'_cold');entry['cold'][mode]={k:cold[k] for k in ('first_present_interval_ms','first_map_cpu_elapsed_ms','setup_cpu_elapsed_ms','present','map_cpu')};entry['cold'][mode]['map_cpu'].pop('fps_from_interval_mean',None)
        for row in rows:
            if row['condition'].endswith('closed') or row['condition']=='ui_disabled':entry['closed'][row['condition']]=row['present']
        areas.append(entry)
    result=dict(schema=1,complete=True,condition_runs=len(report['results']),areas=areas,pose_floor_confirmations=report['areas'],settings=dict(fps_limit=60,workers=0,fog_enabled=True,viewport_size=report['results'][0]['after']['render']['viewport_size'],zoom=report['results'][0]['after']['render']['zoom'],native_process_count=1),sample_discard='First two present and CPU samples of each warm/closed interval discarded; cold intervals retain all samples',frame_clock=report['frame_clock'],map_cpu_clock=report['map_cpu_clock'],limitations=['GPU timestamps and GPU frame time unavailable','UI-disabled is a same-process command, not a startup-disabled executable baseline','Static prototype deliberately has documented visual simplifications','Cold means area/render-path first use; OS, shader and common UI asset caches may be warm','Two short warm repetitions per mode/location; frames are not independent statistical trials','Native pause menu held at fixed copied-save positions; moving gameplay and closed-map lag fixes not established'],interruptions=report.get('interruptions',[]),all_coordinates_claimed=False)
    atomic_json(s/'performance-summary.json',result)
    for e in areas:
        print(json.dumps(dict(area=e['area'],v1=e['warm']['reference'],v2=e['warm']['static'])))
if __name__=='__main__':main()
