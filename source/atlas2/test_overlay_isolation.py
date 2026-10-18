"""CPU-only real read-only game-view fixture; no native game launch or deletion."""
from pathlib import Path
import argparse,hashlib,json,runpy,uuid
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('work',type=Path);p.add_argument('--game',type=Path,required=True);a=p.parse_args();work=a.work.resolve();game=a.game.resolve();before=digest(game/'eboot.bin')
    fixture=work/('overlay-smoke-'+uuid.uuid4().hex[:8]);fixture.mkdir();layer=fixture/'layer';probe=layer/'dvdroot_ps4/atlas2_qa/probe.txt';probe.parent.mkdir(parents=True);probe.write_text('private test only')
    script=work/'Atlas2-test/runtime/port/scripts/mods.py';ns=runpy.run_path(str(script),run_name='atlas2_private_overlay_smoke')
    assert 'print(build_overlay(args.game, args.out, layers, beside_game=False))' in script.read_text()
    output=ns['build_overlay'](game,fixture/'out',[('isolation-test',layer)],beside_game=False);Path(output).resolve().relative_to(fixture)
    assert (Path(output)/'dvdroot_ps4/atlas2_qa/probe.txt').read_text()=='private test only'
    assert digest(game/'eboot.bin')==before
    report=dict(schema=1,pass_=True,native_game_launched=False,output_inside_private_root=True,original_game_executable_unchanged=True,fixture=str(fixture),cleanup='retained locally; no recursive deletion across game links')
    report['pass']=report.pop('pass_');(work/'overlay-isolation-tests.json').write_text(json.dumps(report,indent=2));print('PRIVATE_CROSS_VOLUME_OVERLAY_CPU_PASS')
if __name__=='__main__':main()
