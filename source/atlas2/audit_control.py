"""Small read-only audit-session controller; no travel or arbitrary coordinate command."""
from pathlib import Path
import argparse,json,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from live_protocol import Channel,atomic_json,read_json
from drive_game import graceful_close
def main():
    p=argparse.ArgumentParser();p.add_argument('label');g=p.add_mutually_exclusive_group();g.add_argument('--press',choices=['cross','circle','options','up','down']);g.add_argument('--command',choices=['open','close','recenter','atlas2-static','atlas2-reference','atlas2-audit-flags']);g.add_argument('--graceful-close',action='store_true');a=p.parse_args();w=Path(__file__).resolve().parents[2]/'.local/atlas2';s=(w/'audit-qa/runs'/a.label).resolve();s.relative_to((w/'audit-qa/runs').resolve());c=Channel(s/'map-qa/trace.json.atlas2.json',w/'Atlas2-test/bin/bb-probe.exe',max_age=30);state=c.read()
    if a.graceful_close:graceful_close(c.pid,w/'Atlas2-test/bin/bb-probe.exe');print('PRIVATE_AUDIT_GRACEFUL_CLOSE_REQUESTED');return
    if a.press:
        pad=c.trace.parent/'pad.txt'
        if not pad.is_file():raise RuntimeError('Private pad file missing')
        try:pad.write_text(a.press,encoding='ascii');time.sleep(.35)
        finally:pad.write_text('',encoding='ascii')
        state=c.wait(lambda x:True,after=state['sequence'])
    if a.command:state=c.command(a.command)
    out=dict(native_pid=state['process_id'],pose=state['pose'],open=state['open'],menu_top=state['menu_top'],mode=state['mode'],rendered_layer=state.get('render',{}).get('layer'),measurement=state['measurement'],flag_audit_written=state.get('ack',{}).get('flag_audit_written'))
    atomic_json(s/'audit-status.json',out);print(json.dumps(out))
if __name__=='__main__':main()
