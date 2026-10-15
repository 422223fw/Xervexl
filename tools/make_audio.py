"""Generate original short combat sounds; no external audio assets."""
import math
import random
import struct
import wave
from array import array
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


def music(name,combat=False):
    """Original eight-bar instrumental, with wrapped release tails for a clean loop."""
    rate=22050;beat=60/(88 if combat else 76);duration=beat*32;count=int(duration*rate)
    left=array('f',[0])*count;right=array('f',[0])*count
    rng=random.Random(82 if combat else 19)
    def tone(note,start,length,gain,pan=0,kind='pluck'):
        frequency=440*2**((note-69)/12);first=int(start*rate);samples=int(length*rate)
        for j in range(samples):
            t=j/rate;attack=min(1,t/.018);release=min(1,(length-t)/.13)
            if kind=='pad':value=(math.sin(math.tau*frequency*t)+.23*math.sin(math.tau*frequency*2.003*t))*attack*release*.65
            elif kind=='drum':value=math.sin(math.tau*(65*t+6*(1-math.exp(-t*18))))*math.exp(-t*18)
            elif kind=='shaker':value=rng.uniform(-1,1)*math.exp(-t*55)
            else:value=(math.sin(math.tau*frequency*t)+.32*math.sin(math.tau*frequency*2*t)+.12*math.sin(math.tau*frequency*3*t))*attack*release*math.exp(-t*(3 if combat else 2))
            value*=gain;index=(first+j)%count;left[index]+=value*(1-pan)*.5;right[index]+=value*(1+pan)*.5
    progression=([50,53,57],[46,50,53],[48,52,55],[45,48,52]) if combat else ([45,48,52],[41,45,48],[48,52,55],[43,47,50])
    for bar in range(8):
        chord=progression[bar%4];start=bar*4*beat
        for i,note in enumerate(chord):tone(note+12,start,4.4*beat,.10,-.5+i*.5,'pad')
        for half in range(8):tone(chord[(half+bar)%3]+24,start+half*.5*beat,beat*.9,.17 if half%2==0 else .12,(-1 if half%2 else 1)*.45)
        for pulse in range(4):
            tone(chord[0]-12,start+pulse*beat,beat*.9,.24,0,'pluck')
            if combat or pulse in (0,2):tone(36,start+pulse*beat,.23,.25 if combat else .12,0,'drum')
            tone(60,start+(pulse+.5)*beat,.10,.065 if combat else .035,.2,'shaker')
        if bar in (1,3,5,7):
            for j,step in enumerate((7,10,12,7)):tone(chord[0]+24+step,start+j*beat,beat*.8,.12,-.2)
    peak=max(max(abs(v) for v in left),max(abs(v) for v in right),.001);scale=18000/peak;pcm=array('h')
    for a,b in zip(left,right):pcm.extend((int(a*scale),int(b*scale)))
    with wave.open(str(root/(name+'.wav')),'wb') as out:
        out.setnchannels(2);out.setsampwidth(2);out.setframerate(rate);out.writeframes(pcm.tobytes())

music('menu_music');music('arena_music',True)
