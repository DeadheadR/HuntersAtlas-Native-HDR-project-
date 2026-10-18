"""Fresh, correlated developer telemetry; never starts a process."""
from pathlib import Path
import ctypes,hashlib,json,math,os,time

class ProtocolError(RuntimeError):pass
def read_json(path):
    try:return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError,ValueError):return {}
def atomic_json(path,value):
    path=Path(path);temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(value,indent=2),encoding='utf-8');temp.replace(path)
def valid_pose(p):
    return isinstance(p,dict) and p.get('valid') is True and isinstance(p.get('block'),int) and all(isinstance(p.get(k),(int,float)) and math.isfinite(p[k]) for k in ('x','y','z','yaw'))
def distance(a,b):return math.dist([a[k] for k in ('x','y','z')],[b[k] for k in ('x','y','z')])
def matched_pose(a,b):
    return valid_pose(a) and valid_pose(b) and a['block']==b['block'] and distance(a,b)<=.05 and abs((a['yaw']-b['yaw']+math.pi)%(2*math.pi)-math.pi)<=.01
def process_image(pid):
    api=ctypes.WinDLL('kernel32',use_last_error=True);api.OpenProcess.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32];api.OpenProcess.restype=ctypes.c_void_p
    api.QueryFullProcessImageNameW.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_uint32)];api.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=api.OpenProcess(0x1000,False,pid)
    if not handle:raise ProtocolError('Cannot verify test process identity')
    try:
        n=ctypes.c_uint32(32768);buf=ctypes.create_unicode_buffer(n.value)
        if not api.QueryFullProcessImageNameW(handle,0,buf,ctypes.byref(n)):raise ProtocolError('Cannot read test process identity')
        return Path(buf.value).resolve()
    finally:api.CloseHandle(handle)

def verified_private_image(pid,expected):
    """Accept the runner's private extracted image only when its bytes match."""
    expected=Path(expected).resolve();actual=process_image(pid)
    if actual==expected:return actual
    state=expected.parent.parent/'state'
    try:relative=actual.relative_to(state.resolve())
    except ValueError:raise ProtocolError('Telemetry belongs to a different process')
    if len(relative.parts)!=3 or not relative.parts[0].startswith('session-assets-') or relative.parts[1:]!=('bin',expected.name):
        raise ProtocolError('Telemetry image is outside the private runner layout')
    digest=lambda path:hashlib.sha256(path.read_bytes()).digest()
    if digest(actual)!=digest(expected):raise ProtocolError('Private runner image content mismatch')
    return actual

class Channel:
    def __init__(self,trace,expected_executable=None,*,clock=time.monotonic,wall=time.time,sleep=time.sleep,max_age=5):
        self.trace=Path(trace);self.control=self.trace.parent/'control.txt';self.clock,self.wall,self.sleep=clock,wall,sleep;self.max_age=max_age;self.pid=None
        self.expected_executable=Path(expected_executable).resolve() if expected_executable else None;self.next_id=int(wall()*1_000_000)
        self.deadline=None
    def read(self):
        state=read_json(self.trace)
        if state.get('schema')!=2 or not isinstance(state.get('sequence'),int):raise ProtocolError('Fresh schema-2 telemetry required')
        if abs(self.wall()-state.get('utc_ms',0)/1000)>self.max_age:raise ProtocolError('Stale native telemetry')
        pid=state.get('process_id')
        if not isinstance(pid,int) or pid<=0:raise ProtocolError('Native process identity missing')
        if self.pid is None:
            if self.expected_executable:verified_private_image(pid,self.expected_executable)
            self.pid=pid
        if pid!=self.pid:raise ProtocolError('Native process changed during comparison')
        return state
    def wait(self,predicate,*,after=0,timeout=20):
        stop=self.clock()+timeout;last_error=None
        if self.deadline is not None:stop=min(stop,self.deadline)
        while self.clock()<stop:
            try:
                state=self.read()
                if state['sequence']>after and predicate(state):return state
            except ProtocolError as exc:last_error=exc
            self.sleep(.12)
        raise ProtocolError('Native confirmation timeout'+(': '+str(last_error) if last_error else ''))
    def command(self,command,timeout=20):
        before=self.read()
        if self.control.exists():raise ProtocolError('Another command is pending; refusing overwrite')
        self.next_id+=1;request=self.next_id;temp=self.control.with_suffix('.request.tmp');temp.write_text(f'atlas2-request {request} {command}\n',encoding='ascii')
        try:
            if os.name=='nt':os.rename(temp,self.control)
            else:os.link(temp,self.control);temp.unlink()
        finally:temp.unlink(missing_ok=True)
        state=self.wait(lambda s:s.get('ack',{}).get('id')==request,after=before['sequence'],timeout=timeout)
        if state['ack'].get('command')!=command:raise ProtocolError('Command acknowledgement mismatch')
        return state
    def rendered(self,mode,after,timeout=30):
        def ready(s):
            r=s.get('render',{})
            return s.get('open') is True and r.get('mode')==mode and r.get('preview') is False and valid_pose(r.get('pose')) and (mode==1 or s.get('backend_ready_tiles')==s.get('visible_tiles') and s.get('uploads_this_frame')==0)
        return self.wait(ready,after=after,timeout=timeout)

def classify_comparison(static,reference):
    a,b=static.get('render',{}),reference.get('render',{})
    if not matched_pose(a.get('pose'),b.get('pose')):return dict(status='inconclusive',reason='pose_changed',gameplay_observed=True)
    strict,v1=a.get('strict_layer'),b.get('v1_layer')
    if not isinstance(strict,int) or not isinstance(v1,int) or min(strict,v1)<0:return dict(status='inconclusive',reason='floor_confirmation_missing',gameplay_observed=True)
    result=dict(status='pass',gameplay_observed=True,matched_pose=True,strict_layer=strict,rendered_layer=a.get('layer'),v1_layer=v1,pose_delta=distance(a['pose'],b['pose']),visual_tiles=static.get('visible_tiles',0),visual_acceptance='pending_internal_review')
    if strict!=v1:result.update(status='mismatch',reason='strict_layer_differs_from_v1')
    elif a.get('layer')!=v1:result.update(status='mismatch',reason='hysteresis_or_manual_layer_differs_from_v1')
    if not result['visual_tiles']:result['visual_acceptance']='no_visible_tiles_under_current_reveal_rules'
    return result
