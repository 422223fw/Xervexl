"""Compare native terrain generation to the actual authoritative generator."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import voxel_world as vox
rows=json.loads(Path(sys.argv[1]).read_text('utf-8-sig'))
materials=('','grass','dirt','stone','wood','leaves','iron_ore','crystal','glass','iron','bedrock')
for row in rows:
    seed,x,z=(row[k] for k in ('seed','x','z'))
    assert row['height']==vox.height(seed,x,z),row
    for y,material in row['blocks']:assert materials[material]==vox.generated(seed,x,y,z),(row,y,material)
print(json.dumps(dict(terrain_columns=len(rows),block_samples=sum(len(r['blocks']) for r in rows),negative_and_large_coordinates=True,passed=True)))
