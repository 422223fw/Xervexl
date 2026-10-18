"""Compare actual native renderer segments with the authoritative geometry."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hitboxes as hb
rows=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
maximum=0.
for row in rows:
    hand,tip=hb.weapon_segment(row['fighter'],row['time'])
    for a,b in ((hand,row['hand']),(tip,row['tip'])):
        error=hb.dot(hb.sub(a,b),hb.sub(a,b))**.5;maximum=max(maximum,error)
        if error>.003:raise AssertionError((row['fighter']['attack'],row['fighter']['guard_dir'],row['fighter']['weapon'],error))
print(json.dumps(dict(native_server_weapon_segments=len(rows),maximum_error_metres=round(maximum,6),passed=True)))
