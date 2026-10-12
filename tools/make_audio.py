"""Generate original short combat sounds; no external audio assets."""
import math
import random
import struct
import wave
from pathlib import Path

root = Path(__file__).resolve().parent.parent / "assets"
root.mkdir(exist_ok=True)
rng = random.Random(12)
for name, duration in (("steel", .38), ("fall", .55)):
    values = []
    for i in range(int(duration*22050)):
        t = i/22050
        if name == "steel":
            value = (math.sin(t*2800*math.tau)+.5*math.sin(t*4430*math.tau)+.6*rng.uniform(-1,1))*math.exp(-t*18)*.24
        else:
            value = (math.sin(t*(120-t*60)*math.tau)+.3*rng.uniform(-1,1))*math.exp(-t*9)*.38
        values.append(struct.pack("<h", max(-32767,min(32767,int(value*32767)))))
    with wave.open(str(root/(name+".wav")), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(22050); f.writeframes(b"".join(values))
