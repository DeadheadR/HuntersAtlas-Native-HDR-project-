"""Validate the private bootstrap, copied saves and experimental environment. Never launch native gameplay."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,runpy

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p,name):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def main():
    p=argparse.ArgumentParser();p.add_argument('work',type=Path);a=p.parse_args();work=a.work.resolve();root=work/'Atlas2-test'
    protected=json.loads((work/'protected-state.json').read_text());settings=json.loads((root/'state/profile/settings.json').read_text())
    os.environ.update(APPDATA=str(root/'state/appdata'),BB_ATLAS_PROFILE_ROOT=str(root/'state/profile'),BB_LAUNCHER_SETTINGS_ROOT=str(root/'state/profile'),BB_OWNED_ATLAS_ROOT=str(root))
    core=load(root/'bootstrap/entry.py','atlas2_verify_core');integrated=load(root/'bootstrap/integrated_play.py','atlas2_verify_integrated');contract=core.load_contract(root);core.validate_game_source(contract,settings)
    with core._materialized_asset_paths(contract) as staged:
        paths={**contract['paths'],**core._validated_materialized_paths(contract,staged)}
        feature=load(root/'bootstrap/atlas_feature_config.py','atlas2_verify_features')
        inherited=dict(os.environ,BB_USER_DIR=settings['user_dir'],BB_GPU_USER_DIR=settings['user_dir'],BB_GAME_DIR=settings['game_dir'],BB_DLC_DIR=settings['dlc_dir'],BB_ATLAS_FEATURES=feature.environment(settings)['BB_ATLAS_FEATURES'])
        env=integrated.environment(core,contract,paths,inherited)
        normal=core.game_environment(contract,settings,inherited)
        assert normal['BB_ATLAS2_ENABLED']=='1' and normal['BB_PREP_WORKERS']=='0'
        assert Path(normal['BB_USER_DIR']).is_relative_to(work)
        assert env['BB_ATLAS2_ENABLED']=='1' and env['BB_PREP_WORKERS']=='0'
        assert env['BB_MAP_FOG_ENABLED']=='1'
        if json.loads((root/'atlas2-local.json').read_text()).get('async_loading'):
            assert env.get('BB_ATLAS2_ASYNC_LOAD')=='1' and normal.get('BB_ATLAS2_ASYNC_LOAD')=='1'
        assert Path(env['BB_USER_DIR']).is_relative_to(work)
        configured_packs=Path(json.loads((root/'atlas2-local.json').read_text())['directory']).resolve();configured_packs.relative_to(work)
        assert env['BB_ATLAS2_INDEX_SHA256']==sha(configured_packs/'atlas2-index.json')
        for record in json.loads((Path(env['BB_MAP_DIR'])/'atlas.json').read_text())['maps']:
            data=json.loads((Path(env['BB_MAP_DIR'])/(record['id']+'.json')).read_text())
            assert all(not l['triangles'] and not l['walls'] for l in data['layers'])
        rejected=False
        try:integrated.environment(core,contract,paths,{**inherited,'BB_USER_DIR':str(Path(protected['source_saves']).parent)})
        except ValueError:rejected=True
        assert rejected
    source=Path(protected['source_saves']);unchanged=all(sha(source/k)==v for k,v in protected['source_save_hashes'].items())
    assert unchanged
    report=dict(schema=1,pass_=True,owned_contract_valid=True,geometry_free_normal_assets=True,private_save_guard=True,source_save_files_unchanged=len(protected['source_save_hashes']),fog_default=True,workers=0,native_game_launched=False)
    report['pass']=report.pop('pass_');(work/'isolation-tests.json').write_text(json.dumps(report,indent=2));print('ATLAS2_ISOLATION_PASS')
if __name__=='__main__':main()
