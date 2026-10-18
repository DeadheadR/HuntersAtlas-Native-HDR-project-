"""Start an isolated copied-save session only after parent GPU coordination.

Use the test install's private CPython. A reserved-window label records coordination;
this script does not reserve GPU time itself.
"""
from pathlib import Path
import argparse,hashlib,json,runpy,sys
def main():
    work=Path(__file__).resolve().parents[2]/'.local/atlas2';source=Path(r'D:\Bloodborne\tools\HuntersAtlas-source\source\owned\tests\live_game.py')
    if sys.argv[1:2]!=['--child']:
        p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reserved-window',required=True);p.add_argument('--label',required=True);a=p.parse_args()
        (work/'qa').mkdir(exist_ok=True)
        (work/'qa/coordination.json').write_text(json.dumps(dict(reserved_window=a.reserved_window,native_launch_requested=True)))
        sys.argv=[__file__,a.label]
    ns=runpy.run_path(str(source),run_name='atlas2_borrowed_live_driver');g=ns['main'].__globals__
    g.update(REPO=work.parents[1],QA_ROOT=work/'qa',CANDIDATE=work/'Atlas2-test',__file__=str(Path(__file__).resolve()))
    g['user_map_fog_preference']=lambda:True
    return ns['main']()
if __name__=='__main__':raise SystemExit(main())
