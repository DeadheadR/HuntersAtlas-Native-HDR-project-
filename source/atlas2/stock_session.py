"""One bounded action on the byte-identical private V1 process; never arbitrary memory writes."""
from pathlib import Path
import argparse,json,runpy,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from live_protocol import ProtocolError,atomic_json,read_json,verified_private_image
from drive_game import graceful_close
from capture_ui import capture_ui
def main():
    p=argparse.ArgumentParser();p.add_argument('label');g=p.add_mutually_exclusive_group();g.add_argument('--press',choices=['cross','circle','options','up','down']);g.add_argument('--command',choices=['open','close','recenter','disable','enable']);g.add_argument('--graceful-close',action='store_true');g.add_argument('--capture-ui',action='store_true');a=p.parse_args();w=Path(__file__).resolve().parents[2]/'.local/atlas2';s=(w/'audit-qa/runs'/a.label).resolve();s.relative_to((w/'audit-qa/runs').resolve());root=w/'V1-stock-test';receipt=read_json(s/'launch.json');Path(receipt['user_dir']).resolve().relative_to(w.resolve());core=runpy.run_path(str(root/'bootstrap/entry.py'));known={'bb-probe.exe','bb-play.exe','shadps4.exe','shadps4-qt.exe','bloodborne.exe'};ids=[pid for name,pid in core['_windows_process_names']() if name.casefold() in known]
    if len(ids)!=1:raise ProtocolError('Exactly one native process is required')
    pid=ids[0];verified_private_image(pid,root/'bin/bb-probe.exe');qa=s/'map-qa';trace=qa/'trace.json'
    if a.graceful_close:graceful_close(pid,root/'bin/bb-probe.exe');print('PRIVATE_STOCK_GRACEFUL_CLOSE_REQUESTED');return
    if a.press:
        pad=qa/'pad.txt'
        if not pad.is_file():raise ProtocolError('Private pad input not initialized')
        try:pad.write_text(a.press,encoding='ascii');time.sleep(.35)
        finally:pad.write_text('',encoding='ascii')
    if a.command:
        control=qa/'control.txt'
        if control.exists():raise ProtocolError('Another stock command is pending')
        control.write_text(a.command+'\n',encoding='ascii');end=time.monotonic()+20
        while control.exists() and time.monotonic()<end:time.sleep(.1)
        if control.exists():raise ProtocolError('Stock command consumption timeout')
    if a.capture_ui:
        images=capture_ui(s);atomic_json(s/'latest-stock-ui-capture.json',dict(schema=1,images=images,private=True));print('PRIVATE_FINAL_STOCK_UI_CAPTURED');return
    value=read_json(trace);keys=['valid','block','x','y','z','yaw','menu_top','menu_supported','open','capture','current_layer','zoom','cx','cz','fog_enabled','enabled'];out={k:value.get(k) for k in keys};out.update(native_pid=pid,native_image_verified=True,trace_present=bool(value),trace_age_seconds=time.time()-trace.stat().st_mtime if trace.exists() else None)
    index=read_json(w/'packs/atlas2-index.json')['areas'];block=value.get('block');out['area']=next((e['area'] for e in index if isinstance(block,int) and sum(int(v)<<(24-8*i) for i,v in enumerate(e['region_id'][1:].split('_')[:2]))==(block&0xffff0000)),None);atomic_json(s/'stock-status.json',out);print(json.dumps(out))
if __name__=='__main__':main()
