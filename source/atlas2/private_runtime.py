"""Keep generated game views inside the isolated local install on another volume."""
from pathlib import Path
import hashlib,json

def isolate_overlay(root):
    root=Path(root)
    script=root/'runtime/port/scripts/mods.py'
    source=script.read_text(encoding='utf-8')
    old='print(build_overlay(args.game, args.out, layers))'
    new='print(build_overlay(args.game, args.out, layers, beside_game=False))'
    if old in source:
        if source.count(old)!=1:raise RuntimeError('Unexpected overlay call count')
        script.write_text(source.replace(old,new),encoding='utf-8',newline='\n')
    elif new not in source:raise RuntimeError('Private overlay isolation patch does not apply')
    digest=hashlib.sha256(script.read_bytes()).hexdigest()
    deps_path=root/'dependencies.json';deps=json.loads(deps_path.read_text())
    deps['ordinary_port']['files']['scripts/mods.py']=digest
    deps_path.write_text(json.dumps(deps,indent=2),encoding='utf-8')
    return digest
