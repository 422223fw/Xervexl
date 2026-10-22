"""Deterministic half-metre terrain and shaped blocks shared with the client."""
import math
from functools import lru_cache

CELL=.5
SHAPES=('cube','slab','ramp','pillar','beam')
MATERIALS=('wood','stone','dirt','glass','iron')
HARDNESS={'dirt':.55,'grass':.65,'wood':1.,'leaves':.3,'stone':1.8,'iron_ore':2.8,'crystal':3.4,'glass':.7,'iron':3.}

def noise(seed,x,z):
    n=(int(seed)^((int(x)*374761393)&0xffffffff)^((int(z)*668265263)&0xffffffff))&0xffffffff
    n=((n^(n>>13))*1274126177)&0xffffffff
    return (n^(n>>16))&0xffffff

@lru_cache(maxsize=65536)
def height(seed,x,z):
    def layer(scale):
        gx,gz=x//scale,z//scale;u=(x%scale)/scale;v=(z%scale)/scale
        u=u*u*(3-2*u);v=v*v*(3-2*v)
        a=noise(seed,gx,gz)/16777215;b=noise(seed,gx+1,gz)/16777215
        c=noise(seed,gx,gz+1)/16777215;d=noise(seed,gx+1,gz+1)/16777215
        return (a*(1-u)+b*u)*(1-v)+(c*(1-u)+d*u)*v
    return 4 if abs(x)<=8 and abs(z)<=8 else 3+int(layer(36)*13+layer(12)*3)

@lru_cache(maxsize=131072)
def generated(seed,x,y,z):
    floor=height(seed,x,z)
    if y<=-32:return 'bedrock'
    if y<=floor:
        if y==floor:return 'grass'
        if y>=floor-3:return 'dirt'
        ore=noise(seed+97,x+y*11,z-y*7)%100
        return 'crystal' if y<floor-8 and ore==0 else 'iron_ore' if ore<5 else 'stone'
    for gx in range(x//14-1,x//14+2):
        for gz in range(z//14-1,z//14+2):
            tx=gx*14+3+noise(seed+3,gx,gz)%8;tz=gz*14+3+noise(seed+5,gx,gz)%8
            if abs(tx)<=10 and abs(tz)<=10:continue
            base=height(seed,tx,tz)
            if x==tx and z==tz and base<y<=base+6:return 'wood'
            if base+4<=y<=base+8 and (x-tx)**2+(z-tz)**2+(y-base-6)**2<=10:return 'leaves'
    return ''

def block(record,x,y,z):
    if y<-32 or y>159 or abs(x)>1048576 or abs(z)>1048576:return {'material':'bedrock','shape':'cube','rotation':0} if y<-32 else None
    key=f'{x},{y},{z}'
    if key in record['edits']:return record['edits'][key] or None
    material=generated(record['seed'],x,y,z)
    return dict(material=material,shape='cube',rotation=0) if material else None

def shape_height(b,x,z):
    shape=b.get('shape','cube');rotation=b.get('rotation',0)%4
    for _ in range(rotation):x,z=1-z,x
    if shape=='slab':return .5
    if shape=='ramp':return x
    if shape=='pillar' and (x-.5)**2+(z-.5)**2>.22**2:return 0
    return .65 if shape=='beam' else 1.

def contains(b,x,y,z):
    return (b.get('shape')!='beam' or y>=.35) and y<=shape_height(b,x,z)

def solid(record,x,y,z):
    cx,cy,cz=math.floor(x/CELL),math.floor(y/CELL),math.floor(z/CELL)
    b=block(record,cx,cy,cz)
    return bool(b and contains(b,x/CELL-cx,y/CELL-cy,z/CELL-cz))

def floor_at(record,x,z,ceiling=80.):
    cx,cz=math.floor(x/CELL),math.floor(z/CELL)
    start=min(159,math.floor(ceiling/CELL))
    for y in range(start,-33,-1):
        b=block(record,cx,y,cz)
        if b:
            surface=(y+shape_height(b,x/CELL-cx,z/CELL-cz))*CELL
            if surface<=ceiling+.001 and surface>y*CELL:return surface
    return -16.

def ray(record,start,direction,distance=4.5):
    length=math.sqrt(sum(a*a for a in direction))
    if length<1e-9:return None
    direction=tuple(a/length for a in direction);previous=None;current=None
    for i in range(int(distance/.035)+1):
        travel=min(distance,i*.035);p=tuple(a+b*travel for a,b in zip(start,direction))
        key=tuple(math.floor(a/CELL) for a in p)
        if key!=current:previous,current=current,key
        b=block(record,*key)
        if b and contains(b,*(p[j]/CELL-key[j] for j in range(3))):return dict(cell=key,adjacent=previous,block=b,point=p,distance=travel)
    return None
