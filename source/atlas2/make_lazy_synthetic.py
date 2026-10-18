"""Convert a synthetic-only fixture to external compact per-view metadata."""
from pathlib import Path
import argparse,json,shutil
from pack_format import sha
def main():
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 if a.output.exists():raise RuntimeError('Fresh synthetic output required')
 shutil.copytree(a.source,a.output);area=a.output/'Area01';(area/'objects').mkdir();(area/'views').mkdir();m=json.loads((area/'manifest.json').read_text());b=m['bounds'];headers=[]
 for layer,v in enumerate(m['views']):
  sets=[]
  for g in v['groups']:
   compact=[]
   for t in g['tiles']:
    dst=area/'objects'/(t['sha256']+'.a2t')
    if not dst.exists():shutil.copy2(area/('F'+str(layer))/t['file'],dst)
    compact.append([t['lod'],t['x'],t['y'],t['sha256']])
   g.pop('tiles');g['tile_set']=len(sets);sets.append(compact)
  v.update(schema=1,kind='composite',layer_index=layer,ppu=8,width=m['width'],height=m['height'],levels=1,world_to_image=[8,0,-b[0]*8,0,-8,b[3]*8],tile_sets=sets);file='views/F'+str(layer)+'.json';(area/file).write_text(json.dumps(v));headers.append(dict(kind='external_composite',layer_index=layer,ppu=8,width=m['width'],height=m['height'],levels=1,world_to_image=v['world_to_image'],view_file=file,view_sha256=sha(area/file)))
 m['schema']=3;m['views']=headers;(area/'manifest.json').write_text(json.dumps(m));idx=json.loads((a.output/'atlas2-index.json').read_text());idx['areas'][0]['manifest_sha256']=sha(area/'manifest.json');(a.output/'atlas2-index.json').write_text(json.dumps(idx));print('LAZY_SYNTHETIC_FIXTURE_READY no_game_data=true')
if __name__=='__main__':main()
