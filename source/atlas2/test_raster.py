"""Check floor coverage and source bounds using private tile data; no images emitted."""
from pathlib import Path
from functools import lru_cache
import argparse,json,math,zlib
def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();rows=[]
    @lru_cache(maxsize=32)
    def decode(path):return zlib.decompress(path.read_bytes()[12:])
    for label in ['Area02','Area10']:
        root=a.root/label;m=json.loads((root/'manifest.json').read_text());g=json.loads((root/'grid.json').read_text());by_layer=[]
        for li,view in enumerate(m['views']):
            tiles={}
            for group in view['groups']:
                for t in group['tiles']:
                    if t['lod']==0:tiles.setdefault((t['x'],t['y']),[]).append(root/('F'+str(li))/t['file'])
            by_layer.append(tiles)
        exact=near=missing=outside=0
        for li,v,ys in g['surfaces']:
            for k in [0,2,4]:outside+=not(m['bounds'][0]-.001<=v[k]<=m['bounds'][2]+.001 and m['bounds'][1]-.001<=v[k+1]<=m['bounds'][3]+.001)
            if abs((v[2]-v[0])*(v[5]-v[1])-(v[4]-v[0])*(v[3]-v[1]))<1e-8:continue
            x=(v[0]+v[2]+v[4])/3;z=(v[1]+v[3]+v[5])/3;u=(x-m['bounds'][0])*m['ppu'];w=(m['bounds'][3]-z)*m['ppu'];px=math.floor(u);py=math.floor(w)
            def alpha(dx,dy):
                ax=px+dx;ay=py+dy
                if ax<0 or ay<0:return False
                return any(decode(path)[((ay%256+2)*260+ax%256+2)*4+3]>0 for path in by_layer[li].get((ax//256,ay//256),[]))
            if alpha(0,0):exact+=1
            elif any(alpha(dx,dy) for dx in [-1,0,1] for dy in [-1,0,1]):near+=1
            else:missing+=1
        rows.append(dict(area=label,centroids_covered_exact_pixel=exact,centroids_within_one_pixel=near,missing=missing,vertices_outside_declared_bounds=outside))
    report=dict(schema=1,areas=rows,pass_=all(r['missing']==0 and r['vertices_outside_declared_bounds']==0 for r in rows),kind='finite offline raster coverage; not navigation visual acceptance');report['pass']=report.pop('pass_');(a.root.parent/'raster-tests.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':main()
