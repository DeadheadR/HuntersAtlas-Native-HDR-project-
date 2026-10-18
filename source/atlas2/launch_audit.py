"""Guarded launch for exact stock V1 or instrumented Atlas2, from the same frozen copied save."""
from pathlib import Path
import argparse,hashlib,json,runpy,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from launch_session import verify_lease
def main():
    work=Path(__file__).resolve().parents[2]/'.local/atlas2';coord=work/'audit-qa/coordination.json'
    if sys.argv[1:2]!=['--child']:
        p=argparse.ArgumentParser();p.add_argument('--reserved-window',required=True);p.add_argument('--label',required=True);p.add_argument('--variant',choices=['stock_trace','stock_clean','atlas2_audit'],required=True);p.add_argument('--template-id');a=p.parse_args();verify_lease(work,a.reserved_window);template=work/'audit-template/savedata'
        if a.template_id:
            approved=json.loads((work/'approved-copy-inspection.json').read_text());copy=next((c for c in approved['copies'] if c['candidate']==a.template_id and c['source_receipt_verified']),None)
            if copy is None:raise RuntimeError('Only a previously inspected approved copy is allowed')
            template=Path(copy['template']);template.resolve().relative_to((work/'audit-save-templates').resolve())
        content=Path(r'D:\Bloodborne\tools\HuntersAtlas-source\source\owned\tests\live_game.py').read_text();anchor='        return result\n';assert content.count(anchor)==1
        # Keep stock native behavior, with optional removal of the expensive legacy QA trace.
        insert='        result["BB_FPS_LOG"]="1"\n        if json.loads((QA_ROOT/"coordination.json").read_text())["variant"]=="stock_clean":result.pop("BB_MAP_TEST_TRACE",None)\n'
        content=content.replace(anchor,insert+anchor);identity=hashlib.sha256(content.encode()).hexdigest();coord.parent.mkdir(exist_ok=True);snapshot=coord.parent/('audit-driver-'+identity[:16]+'.py');snapshot.write_text(content,encoding='utf-8',newline='\n');coord.write_text(json.dumps(dict(reserved_window=a.reserved_window,variant=a.variant,template=str(template),driver_path=str(snapshot),driver_sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest())));sys.argv=[__file__,a.label]
    info=json.loads(coord.read_text());verify_lease(work,info['reserved_window']);snapshot=Path(info['driver_path']);snapshot.resolve().relative_to(coord.parent.resolve());assert hashlib.sha256(snapshot.read_bytes()).hexdigest()==info['driver_sha256'];ns=runpy.run_path(str(snapshot),run_name='atlas2_audit_borrowed_driver');g=ns['main'].__globals__;candidate=work/('Atlas2-test' if info['variant']=='atlas2_audit' else 'V1-stock-test');template=Path(info.get('template',str(work/'audit-template/savedata')));template.resolve().relative_to(work.resolve());g.update(REPO=work.parents[1],QA_ROOT=coord.parent,CANDIDATE=candidate,SOURCE_SAVEDATA=template,__file__=str(Path(__file__).resolve()));g['user_map_fog_preference']=lambda:True
    return ns['main']()
if __name__=='__main__':raise SystemExit(main())
