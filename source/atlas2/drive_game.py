"""One named logical input, or graceful OS close, for this verified private test process."""
from pathlib import Path
import argparse,ctypes,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from live_protocol import Channel,ProtocolError,process_image

def graceful_close(pid,expected):
    if process_image(pid)!=expected.resolve():raise ProtocolError('Refusing to close a different process')
    user=ctypes.WinDLL('user32',use_last_error=True);callback_type=ctypes.WINFUNCTYPE(ctypes.c_int,ctypes.c_void_p,ctypes.c_void_p);windows=[]
    user.GetWindowThreadProcessId.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint32)];user.PostMessageW.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_size_t,ctypes.c_ssize_t]
    @callback_type
    def callback(window,_):
        owner=ctypes.c_uint32();user.GetWindowThreadProcessId(window,ctypes.byref(owner))
        if owner.value==pid:windows.append(window)
        return 1
    user.EnumWindows.argtypes=[callback_type,ctypes.c_void_p];user.EnumWindows(callback,None)
    if not windows:raise ProtocolError('No private test window found for graceful close')
    for window in windows:
        if not user.PostMessageW(window,0x0010,0,0):raise ProtocolError('Graceful close request failed')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('label');g=p.add_mutually_exclusive_group(required=True);g.add_argument('--press',choices=['cross','circle','square','triangle','options','up','down','left','right']);g.add_argument('--graceful-close',action='store_true');a=p.parse_args()
    work=Path(__file__).resolve().parents[2]/'.local/atlas2';session=(work/'qa/runs'/a.label).resolve();session.relative_to((work/'qa/runs').resolve());trace=session/'map-qa/trace.json.atlas2.json';expected=work/'Atlas2-test/bin/bb-probe.exe';channel=Channel(trace,expected);state=channel.read()
    if a.graceful_close:graceful_close(state['process_id'],expected);print('PRIVATE_TEST_GRACEFUL_CLOSE_REQUESTED');return
    # A continuously updating native trace is required before sending a single input.
    channel.wait(lambda s:True,after=state['sequence']);pad=trace.parent/'pad.txt'
    if not pad.is_file():raise ProtocolError('Private logical input file missing')
    try:pad.write_text(a.press,encoding='ascii');time.sleep(.25)
    finally:pad.write_text('',encoding='ascii')
    print('PRIVATE_LOGICAL_BUTTON_SENT')
if __name__=='__main__':main()
