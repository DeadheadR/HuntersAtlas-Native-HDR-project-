"""Spoiler-free planned/live coverage. Offline samples never become gameplay passes."""
from pathlib import Path
import argparse,json

def main():
    p=argparse.ArgumentParser();p.add_argument('work',type=Path);p.add_argument('--session',type=Path);a=p.parse_args();work=a.work.resolve();index=json.loads((work/'packs/atlas2-index.json').read_text());rows=[]
    live=[]
    if a.session:
        a.session.resolve().relative_to(work)
        result=a.session/'comparison-summary.json'
        if result.is_file():live=json.loads(result.read_text()).get('results',[])
    for entry in index['areas']:
        m=json.loads((work/'packs'/entry['area']/'manifest.json').read_text());area_live=[r for r in live if r.get('area')==entry['area']]
        layers=[]
        for i,layer in enumerate(m['layers']):
            observed=[r for r in area_live if r.get('strict_layer')==i and r.get('arrival_confirmed')]
            layers.append(dict(layer_id=f'F{i:03}',source_layer=i,offline_footprint=layer['footprint'],live_status='mismatch' if any(r.get('status')=='mismatch' for r in observed) else 'sampled_match' if any(r.get('status')=='pass' for r in observed) else 'unverified',live_destination_samples=len(observed)))
        rows.append(dict(area=entry['area'],layers=layers,live_destination_attempts=len(area_live),coverage_gap_reason='No confirmed eligible copied-save destination sample for each unverified layer'))
    report=dict(schema=1,finite_sample=True,offline_coverage_source=str(work/'all-area-tests.json'),offline_probe_counts_are_not_gameplay_coverage=True,areas=rows,live_destination_attempts=len(live),live_matches=sum(r.get('status')=='pass' for r in live),live_mismatches=sum(r.get('status')=='mismatch' for r in live),all_coordinates_claimed=False,planned_performance_conditions=['disabled','enabled_closed','map_open_static','map_open_reference'],performance_status='unmeasured')
    (work/'live-coverage-manifest.json').write_text(json.dumps(report,indent=2));print('COVERAGE_MANIFEST areas='+str(len(rows))+' layers='+str(sum(len(r['layers']) for r in rows))+' live_attempts='+str(len(live)))
if __name__=='__main__':main()
