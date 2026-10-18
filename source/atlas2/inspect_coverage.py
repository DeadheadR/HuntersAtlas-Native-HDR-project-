"""Offline, anonymous inventory of authored guarded targets and copied-save candidates."""
from pathlib import Path
import argparse,hashlib,json,os,re

def main():
    p=argparse.ArgumentParser();p.add_argument('work',type=Path);a=p.parse_args();w=a.work.resolve();f=json.loads((w/'reference-assets/maps/features.json').read_text());index=json.loads((w/'packs/atlas2-index.json').read_text());rows=[]
    for e in index['areas']:
        data=f['areas'][e['region_id']];lamps=data.get('lamps',[])
        rows.append(dict(area=e['area'],authored_lamps=len(lamps),lamp_field_names=sorted(set(k for l in lamps for k in l)),native_entry_types=[type(l.get('native')).__name__ for l in lamps]))
    report=dict(schema=1,areas=rows)
    (w/'coverage-offline-inventory.json').write_text(json.dumps(report,indent=2));print(json.dumps(rows))
    source=Path(__file__).resolve().parents[1]/'native/gpu/shim/bbport_map_features.cpp'
    print('ELIGIBILITY_CODE')
    print('\n'.join(re.sub(r'"[^"\n]*"','"STR"',line) for line in source.read_text().splitlines() if '.available=' in line or '.discovered=' in line or 'travel_supported' in line))
if __name__=='__main__':main()
