from pathlib import Path
import os,sys
P=Path(__file__).resolve().parent
sys.path.insert(0,str(P))
from config import MAP_ID,WORK,SRC
sys.path.insert(0,str(SRC))
import numpy as np
import pipeline_context as c
from config import GAME_DIR
c.configure(GAME_DIR,WORK/'extract')
import soulstruct_local_config
sys.modules['soulstruct.config']=soulstruct_local_config
from generate_floorplans_v12 import all_geometry
t,fail=all_geometry(c.GAME,MAP_ID)
np.save(WORK/'collision.npy',t.astype(np.float32))
(WORK/'collision-extraction-qa.json').write_text(__import__('json').dumps({'map_id':MAP_ID,'triangles':len(t),'omissions':fail},indent=2))
print('EXTRACTED',MAP_ID,len(t),'OMISSIONS',len(fail),flush=True)
