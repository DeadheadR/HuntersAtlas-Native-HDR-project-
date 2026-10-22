"""Initialize this extracted, self-contained package for Bloodborne 1.09."""
from pathlib import Path
import argparse,importlib.util,json,os,subprocess,sys,datetime,shutil
ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
def read(path):
 try:return json.loads(path.read_text(encoding='utf-8-sig'))
 except (OSError,ValueError):return {}
def write(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix(path.suffix+'.tmp');temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(temporary,path)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--game',type=Path);parser.add_argument('--user-dir',type=Path);parser.add_argument('--profile-source',type=Path);parser.add_argument('--no-open',action='store_true');args=parser.parse_args()
 core=load('atlas_compact_install_core',ROOT/'bootstrap/entry.py');contract=core.load_contract(ROOT);core.ensure_no_game_processes()
 lock=ROOT/'state/ui.lock'
 if lock.exists() and core._pid_alive(read(lock).get('pid',-1)):raise ValueError('Close this Atlas launcher before running Install.cmd.')
 profile=ROOT/'state/profile/settings.json';ordinary=args.profile_source or Path(os.environ.get('APPDATA',Path.home()/'AppData/Roaming'))/'bbport-launcher/settings.json'
 settings=read(profile) or read(ordinary);candidates=[]
 if args.game:candidates.append(args.game)
 elif settings.get('game_dir'):candidates.append(Path(settings['game_dir']))
 if not args.game:
  for parent in list(ROOT.parents)[:3]:
   candidates += [parent,parent/'Image0',parent/'CUSA00207',parent/'CUSA03173']
 game=None
 for candidate in candidates:
  if (candidate/'eboot.bin').is_file():
   try:core.validate_game_source(contract,{'game_dir':str(candidate)});game=candidate.resolve();break
   except core.BootstrapError:
    if args.game:raise
 if game is None:
  if args.game:raise ValueError('The selected game folder has no supported 1.09 eboot.bin.')
  import tkinter as tk
  from tkinter import filedialog
  window=tk.Tk();window.withdraw()
  selected=filedialog.askdirectory(parent=window,title='Select Bloodborne 1.09 folder containing eboot.bin',mustexist=True);window.destroy()
  if not selected:raise ValueError('Installation canceled. No game files were changed.')
  game=Path(selected).resolve();core.validate_game_source(contract,{'game_dir':str(game)})
 state=ROOT/'state';port=state/'port';port.mkdir(parents=True,exist_ok=True)
 stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f');backup=state/'install-backups'/stamp
 for path in (profile,port/'input.ini',port/'bbport.ini',port/'settings.ini'):
  if path.is_file():
   dest=backup/path.relative_to(state);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
 user=args.user_dir or (Path(settings['user_dir']) if str(settings.get('user_dir','')).strip() else state/'user')
 if not user.is_absolute():user=ROOT/user
 # The user's existing saves remain in their selected location. The package
 # contains none; tests can explicitly supply a copied save directory.
 settings.update(game_dir=str(game),user_dir=str(user.resolve()),atlas_dir=str(ROOT),atlas_enabled=True,check_updates=False)
 settings.setdefault('atlas_fog_enabled',False);settings.setdefault('atlas_travel_enabled',True)
 settings.setdefault('atlas_items_enabled',True);settings.setdefault('atlas_npc_mode','new_dialogue')
 settings.setdefault('ui_language','en')
 if not str(settings.get('dlc_dir','')).strip() and (game.parent/'DLC').is_dir():settings['dlc_dir']=str(game.parent/'DLC')
 inputs=load('atlas_compact_inputs',ROOT/'integration/ui/bbport_input_config.py')
 input_file=port/'input.ini';content=input_file.read_text(encoding='utf-8') if input_file.is_file() else inputs.DEFAULT_INPUT_INI
 import re
 if re.search(r'^\s*#?\s*mouse_to_joystick\s*=',content,re.M):content=re.sub(r'^\s*#?\s*mouse_to_joystick\s*=.*$', 'mouse_to_joystick = right',content,flags=re.M)
 else:content+='\nmouse_to_joystick = right\n'
 input_file.write_text(content,encoding='utf-8')
 (port/'settings.ini').write_text('[map]\nenabled=1\nkeyboard=0\ncontroller=0\n',encoding='utf-8')
 write(profile,settings)
 receipt=dict(schema=1,format='compiled-vector-v1',game_build='1.09',game_sha256=core.SUPPORTED_GAME_SHA256,atlas_enabled=True,mouse_look_enabled=True,game_files_changed=False,existing_launcher_required=False,initialized_at=stamp)
 write(state/'installation/compact-receipt.json',receipt)
 print("Hunter's Atlas 3.0 is ready. Open HuntersAtlas.exe, check Mods & patches, then press Play.")
 if not args.no_open:subprocess.Popen([str(contract['pythonw']),'-I','-B',str(ROOT/'owned/app.py')],cwd=ROOT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
if __name__=='__main__':
 try:main()
 except Exception as error:print("Hunter's Atlas installation: "+str(error),file=sys.stderr);raise SystemExit(1)
