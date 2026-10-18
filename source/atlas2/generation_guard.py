"""Single-writer guard for private CPU bake output; queries only process identity."""
from pathlib import Path
import ctypes,json,msvcrt,os
class Basic(ctypes.Structure):
 _fields_=[('exit_status',ctypes.c_long),('peb',ctypes.c_void_p),('affinity',ctypes.c_size_t),('priority',ctypes.c_long),('pid',ctypes.c_size_t),('parent',ctypes.c_size_t)]
class Time(ctypes.Structure):_fields_=[('low',ctypes.c_uint32),('high',ctypes.c_uint32)]
def snapshot(pid):
 kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.OpenProcess.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32];kernel.OpenProcess.restype=ctypes.c_void_p;kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.QueryFullProcessImageNameW.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_uint32)];kernel.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint32)];kernel.GetProcessTimes.argtypes=[ctypes.c_void_p,*([ctypes.POINTER(Time)]*4)];h=kernel.OpenProcess(0x100400,False,int(pid))
 if not h:
  if ctypes.get_last_error()==5:raise PermissionError('Cannot inspect recorded generation process; do not duplicate it')
  return None
 try:
  code=ctypes.c_uint32();creation,exit,kern,user=Time(),Time(),Time(),Time();buf=ctypes.create_unicode_buffer(32768);n=ctypes.c_uint32(len(buf));basic=Basic();nt=ctypes.WinDLL('ntdll');nt.NtQueryInformationProcess.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p]
  if not kernel.GetExitCodeProcess(h,ctypes.byref(code)) or code.value!=259 or not kernel.QueryFullProcessImageNameW(h,0,buf,ctypes.byref(n)) or not kernel.GetProcessTimes(h,ctypes.byref(creation),ctypes.byref(exit),ctypes.byref(kern),ctypes.byref(user)):return None
  if nt.NtQueryInformationProcess(h,0,ctypes.byref(basic),ctypes.sizeof(basic),None)<0:return None
  return dict(pid=int(pid),parent_pid=int(basic.parent),image=str(Path(buf.value).resolve()),creation=(creation.high<<32)|creation.low)
 finally:kernel.CloseHandle(h)
def same(record):
 now=snapshot(record['pid']);return now is not None and now['creation']==record['creation'] and now['image'].casefold()==record['image'].casefold()
def acquire(root):
 root=Path(root);owner=root/'generation-owner.json'
 if owner.exists() and same(json.loads(owner.read_text())):raise RuntimeError('Existing CPU generation controller is alive; do not duplicate it')
 state=root/'generation-state.json'
 if state.exists():
  old=json.loads(state.read_text());worker=snapshot(old.get('worker_pid',0))
  if old.get('state')=='running' and worker and Path(worker['image']).name.startswith('atlas2-parity-bake'):raise RuntimeError('Existing CPU bake worker is alive; reconcile before resume')
 lock=(root/'.generation.lock').open('a+b')
 if lock.tell()==0:lock.write(b'\0');lock.flush()
 lock.seek(0)
 try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
 except OSError:lock.close();raise RuntimeError('Another writer owns this generation directory')
 record=snapshot(os.getpid())
 if record is None:lock.close();raise RuntimeError('Cannot verify generation controller identity')
 tmp=owner.with_suffix('.tmp');tmp.write_text(json.dumps(record));os.replace(tmp,owner);return lock
