import sys
import time
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import Arena
runtime=Path(__file__).resolve().parents[1]/'data'/'simulation'
runtime.mkdir(parents=True,exist_ok=True)
temporary=tempfile.TemporaryDirectory(dir=runtime)
a=Arena(Path(temporary.name)/"accounts.json",seed=4)
start=time.monotonic()
for _ in range(900): a.tick(1/30)
print(dict(simulated_seconds=30,wall_seconds=round(time.monotonic()-start,2),kills=sum(f["kills"] for f in a.fighters.values()),attacks=sum(f["attack_id"] for f in a.fighters.values()),health=[round(f["hp"]) for f in a.fighters.values()]))
print([(f["name"],f["action"],round(f["x"],1),round(f["z"],1)) for f in a.fighters.values()])
a.learning_close()
restored=Arena(a.path,seed=4)
print(dict(learning_samples=a.learning.updates,contexts=len(a.learning.values),restart_preserves_memory=restored.learning.values==a.learning.values))
temporary.cleanup()
