"""Start an isolated copied-save session only after parent GPU coordination.

Use the test install's private CPython. A reserved-window label records coordination;
this script does not reserve GPU time itself.
"""
from pathlib import Path
import argparse,ctypes,datetime,hashlib,json,re,runpy,sys
def verify_lease(work,reservation):
    record=json.loads((work/'native-lease.json').read_text(encoding='utf-8-sig'))
    if record.get('state')!='held' or record.get('reservation')!=reservation:raise RuntimeError('Matching parent-reserved native lease required')
    stamp=datetime.datetime.fromisoformat(re.sub(r'(\.\d{6})\d+',r'\1',record['heartbeat_utc']).replace('Z','+00:00'))
    if abs((datetime.datetime.now(datetime.timezone.utc)-stamp).total_seconds())>4:raise RuntimeError('Native lease heartbeat is stale')
    api=ctypes.WinDLL('kernel32',use_last_error=True);api.OpenMutexW.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_wchar_p];api.OpenMutexW.restype=ctypes.c_void_p;api.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32];api.ReleaseMutex.argtypes=[ctypes.c_void_p];api.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=api.OpenMutexW(0x100001,False,'Local\\Piranesi.Validation.SingleWorker')
    if not handle:raise RuntimeError('Cannot verify shared native lease')
    try:
        result=api.WaitForSingleObject(handle,0)
        if result in (0,128):api.ReleaseMutex(handle);raise RuntimeError('Shared native lease is not held')
        if result!=258:raise RuntimeError('Shared native lease check failed')
    finally:api.CloseHandle(handle)
def main():
    work=Path(__file__).resolve().parents[2]/'.local/atlas2';source=Path(r'D:\Bloodborne\tools\HuntersAtlas-source\source\owned\tests\live_game.py')
    if sys.argv[1:2]!=['--child']:
        p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reserved-window',required=True);p.add_argument('--label',required=True);a=p.parse_args()
        verify_lease(work,a.reserved_window)
        (work/'qa').mkdir(exist_ok=True)
        content=source.read_bytes();identity=hashlib.sha256(content).hexdigest();snapshot=work/'qa'/('borrowed-live-driver-'+identity[:16]+'.py')
        if not snapshot.exists():snapshot.write_bytes(content)
        (work/'qa/coordination.json').write_text(json.dumps(dict(reserved_window=a.reserved_window,native_launch_requested=True,driver_path=str(snapshot),driver_sha256=identity)))
        sys.argv=[__file__,a.label]
    coordination=json.loads((work/'qa/coordination.json').read_text());snapshot=Path(coordination['driver_path']);snapshot.resolve().relative_to((work/'qa').resolve())
    if hashlib.sha256(snapshot.read_bytes()).hexdigest()!=coordination['driver_sha256']:raise RuntimeError('Borrowed test driver identity mismatch')
    ns=runpy.run_path(str(snapshot),run_name='atlas2_borrowed_live_driver');g=ns['main'].__globals__
    g.update(REPO=work.parents[1],QA_ROOT=work/'qa',CANDIDATE=work/'Atlas2-test',__file__=str(Path(__file__).resolve()))
    g['user_map_fog_preference']=lambda:True
    original_child=g['run_integrated_child']
    def guarded_child(label):
        coordination=json.loads((work/'qa/coordination.json').read_text())
        verify_lease(work,coordination['reserved_window'])
        return original_child(label)
    g['run_integrated_child']=guarded_child
    return ns['main']()
if __name__=='__main__':raise SystemExit(main())
