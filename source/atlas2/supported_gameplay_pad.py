"""Bounded ordinary movement through the pinned runtime's existing BB_PAD_FILE hook."""
from pathlib import Path
import argparse,os,re,time
from launch_session import verify_lease
from live_protocol import Channel
def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--reserved-window',required=True);p.add_argument('--tokens',required=True);p.add_argument('--hold-ms',type=int,default=250);a=p.parse_args();w=Path(__file__).resolve().parents[2]/'.local/atlas2';s=a.session.resolve();s.relative_to(w.resolve());verify_lease(w,a.reserved_window)
 if not 20<=a.hold_ms<=1500:raise RuntimeError('Movement duration bound is 20..1500 ms')
 tokens=a.tokens.split()
 if not tokens or any(t!='circle' and not re.fullmatch(r'[lr][xy]=(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])',t) for t in tokens):raise RuntimeError('Only existing stick tokens and circle are allowed')
 c=Channel(s/'map-qa/trace.json.atlas2.json',w/'Atlas2-test/bin/bb-probe.exe',max_age=30);before=c.read()
 if not before['pose']['valid'] or before['open'] or before['menu_top']:raise RuntimeError('Loaded gameplay with both menus closed is required')
 pad=c.trace.parent/'pad.txt'
 def write(text):
  tmp=pad.with_name('pad.movement.tmp');tmp.write_text(text,encoding='ascii');os.replace(tmp,pad)
 try:write(' '.join(tokens));time.sleep(a.hold_ms/1000)
 finally:write('')
 c.wait(lambda x:True,after=before['sequence']);print('SUPPORTED_GAMEPLAY_INPUT_RELEASED')
if __name__=='__main__':main()
