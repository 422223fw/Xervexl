"""Compound body hitboxes and weapon segments from the native animation curves.

combat_geometry.json is exported from src/poses.hpp at build time. It contains
poses, not outcomes; every collision is calculated from current server state.
"""
import json
import math
import time
from pathlib import Path

def read_geometry(path):
    # Windows can briefly deny a reader during atomic replacement by a build.
    for attempt in range(7):
        try:return json.loads(path.read_text(encoding='utf-8'))
        except PermissionError:
            if attempt==6:raise
            time.sleep(.01*(attempt+1))

DATA=read_geometry(Path(__file__).resolve().parent/'assets'/'combat_geometry.json')
MELEE={'blade','spear','axe','mace','unarmed'}
GUARD_TIME=.12

def add(a,b):return (a[0]+b[0],a[1]+b[1],a[2]+b[2])
def sub(a,b):return (a[0]-b[0],a[1]-b[1],a[2]-b[2])
def mul(a,s):return (a[0]*s,a[1]*s,a[2]*s)
def dot(a,b):return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def norm(a):return mul(a,1/max(.0001,math.sqrt(dot(a,a))))
def clamp(x,a,b):return max(a,min(b,x))
def mix(a,b,t):return tuple(x+(y-x)*t for x,y in zip(a,b))
def smooth(t):t=clamp(t,0,1);return t*t*t*(10+t*(-15+6*t))
def wrapped(a):return (a+math.pi)%math.tau-math.pi

def blend(a,b,t):
    yaw=math.atan2(a[3],a[5]);pitch=math.atan2(a[4],math.hypot(a[3],a[5]))
    yaw+=wrapped(math.atan2(b[3],b[5])-yaw)*t
    pitch+=(math.atan2(b[4],math.hypot(b[3],b[5]))-pitch)*t
    return (*mix(a[:3],b[:3],t),math.sin(yaw)*math.cos(pitch),math.sin(pitch),math.cos(yaw)*math.cos(pitch),
            a[6]+wrapped(b[6]-a[6])*t,a[7]+wrapped(b[7]-a[7])*t,a[8]+(b[8]-a[8])*t)

def walking_pose(f):
    base=DATA['idle'];yaw=f['yaw'] if f.get('attack') else f.get('body_yaw',f['yaw'])
    x,z=f.get('move_x',0),f.get('move_z',0)
    side=(x*math.cos(yaw)-z*math.sin(yaw))/4.4;forward=(x*math.sin(yaw)+z*math.cos(yaw))/4.4
    magnitude=math.hypot(side,forward);scale=1/max(1,magnitude);side*=scale;forward*=scale;speed=min(1,magnitude)
    gait=f.get('gait',0);stride=math.sin(gait)
    hand=add(base[:3],(side*.075+stride*.025*speed,(.02+(1-math.cos(gait*2))*.012)*speed,forward*.06-abs(side)*.025+math.cos(gait)*.018*speed))
    angle=math.atan2(base[3],base[5])+side*.32+stride*.045*speed
    pitch=math.atan2(base[4],math.hypot(base[3],base[5]))-forward*.16+math.cos(gait)*.035*speed
    return (*hand,math.sin(angle)*math.cos(pitch),math.sin(pitch),math.cos(angle)*math.cos(pitch),side*.06,0,0)

def pose(f,clock,age=None):
    if f.get('block'):
        target=DATA['guards'][f.get('guard_dir','centre')]
        source=f.get('guard_from');elapsed=clock-f.get('guard_changed',-999)
        return blend(source,target,smooth(elapsed/GUARD_TIME)) if source and elapsed<GUARD_TIME else target
    if f.get('build_mode') and f.get('mine_progress',0)>0:
        move=DATA['moves']['overhead'];samples=move['aims']['legs'];position=((clock-f.get('mining_started',clock))%.85)/.85*DATA['intervals'];index=min(len(samples)-2,int(position));result=list(mix(samples[index],samples[index+1],position-index));result[3:6]=norm(result[3:6]);return result
    move=DATA['moves'].get(f.get('attack',''))
    if not move:return walking_pose(f)
    age=clock-f.get('attack_started',clock) if age is None else age
    duration=f.get('attack_duration',move['duration'])
    if age<0 or age>=duration:return walking_pose(f)
    samples=move['aims'][f.get('aim_zone','body')];position=age/duration*DATA['intervals']
    index=min(len(samples)-2,int(position))
    # Normalized linear interpolation is sub-millimetre at this sample density.
    result=list(mix(samples[index],samples[index+1],position-index));result[3:6]=norm(result[3:6])
    return result

def guard_origin(f,clock):
    """Keep the current world blade continuous when entering the look-space guard."""
    p=pose(f,clock);old=(f['yaw'] if f.get('block') or f.get('attack') else f.get('body_yaw',f['yaw']))+p[7]
    before=axes(old);after=axes(f['yaw']);hand=local(p[:3],before);direction=local(p[3:6],before)
    return [*(dot(hand,a) for a in after),*(dot(direction,a) for a in after),wrapped(p[6]+p[7]),0,p[8]]

def blade_length(weapon):
    return .55 if weapon in ('knife','dagger') else 1.85 if weapon=='greatsword' else 2.3 if weapon in ('spear','halberd') else 1.5 if weapon=='longsword' else 1.35 if weapon=='estoc' else .22 if weapon=='fists' else 1.15

def two_handed(f):return not f.get('shield') and f['weapon'] in ('longsword','greatsword','katana','spear','halberd')
def axes(yaw):return (math.cos(yaw),0,-math.sin(yaw)),(0,1,0),(math.sin(yaw),0,math.cos(yaw))
def local(v,basis):return add(add(mul(basis[0],v[0]),mul(basis[1],v[1])),mul(basis[2],v[2]))
def limit(root,end,maximum=.70):
    delta=sub(end,root);length=math.sqrt(dot(delta,delta))
    return add(root,mul(delta,maximum/length)) if length>maximum else end

def joint(root,end,bend,length):
    delta=sub(end,root);distance=clamp(math.sqrt(dot(delta,delta)),.001,2*length-.001);axis=norm(delta)
    outward=sub(bend,mul(axis,dot(bend,axis)))
    if dot(outward,outward)<.0001:
        outward=(0,axis[2],-axis[1])
    return add(add(root,mul(axis,distance*.5)),mul(norm(outward),math.sqrt(max(0,length*length-distance*distance*.25))))


def foot_step(gait,speed,leg):
    speed=clamp(speed,0,1);phase=(gait/math.tau+(.5 if leg<0 else 0))%1
    if phase<.60:return (.27-.9*phase)*speed,0.
    t=(phase-.60)/.40;t2=t*t;t3=t2*t;t4=t3*t;t5=t4*t
    travel=(1-10*t3+15*t4-6*t5)*(-.27)+(t-6*t3+8*t4-3*t5)*(-.9)*.4+(10*t3-15*t4+6*t5)*.27+(-4*t3+7*t4-3*t5)*(-.9)*.4
    return travel*speed,.13*math.sin(math.pi*t)**2*speed


def free_hand_offset(f):
    if f.get('block'):return (-.18,1.37,.48) if f.get('shield') else (-.28,1.08,.03)
    speed=min(1,math.hypot(f.get('move_x',0),f.get('move_z',0))/4.4);gait=f.get('gait',0)
    return -.37,1.19+(1-math.cos(gait*2))*.012*speed,.21+math.sin(gait)*.12*speed

def skeleton(f,clock,age=None):
    p=pose(f,clock,age);body=f.get('body_yaw',f['yaw'])+p[7]+p[6]
    basis=axes(body);blade_yaw=(f['yaw'] if f.get('block') or f.get('attack') else f.get('body_yaw',f['yaw']))+p[7]
    blade_basis=axes(blade_yaw)
    right=local((.34,1.43,0),basis);left=local((-.34,1.43,0),basis)
    hand=local(p[:3],blade_basis);direction=norm(local(p[3:6],blade_basis))
    for _ in range(24 if two_handed(f) else 1):
        hand=limit(right,hand)
        if two_handed(f):hand=add(limit(left,sub(hand,mul(direction,.11))),mul(direction,.11))
    tip=add(hand,mul(direction,blade_length(f['weapon'])))
    other=sub(hand,mul(direction,.11)) if two_handed(f) else limit(left,local(free_hand_offset(f),basis))
    lift=math.sin((.55-f.get('jump',0))/.55*math.pi)*.65 if f.get('jump',0)>0 else 0
    fall=.8 if f.get('downed',0)>0 else f.get('fall',0)
    duration=1.25 if f.get('downed',0)>0 else f.get('fall_duration',1.25)
    tilt=min(1,(duration-fall)*7)*min(1,fall*4)*math.pi*.48 if fall>0 else 0
    front=basis[2];side=basis[0]
    def rotate(v):
        if not tilt:return v
        y=v[1];z=dot(v,front)
        return add(add(mul(side,dot(v,side)),(0,y*math.cos(tilt)-z*math.sin(tilt),0)),mul(front,y*math.sin(tilt)+z*math.cos(tilt)))
    origin=(f['x'],f.get('y',0.)+lift+(.08 if tilt else 0),f['z'])
    def world(v):return add(origin,rotate(v))
    return p,basis,right,left,hand,tip,other,world,rotate

def weapon_segment(f,clock,age=None):
    *_,hand,tip,other,world,rotate=skeleton(f,clock,age)
    if f['weapon']=='fists':tip=hand
    elif f.get('attack')=='pommel':tip=sub(hand,mul(norm(sub(tip,hand)),.20))
    return world(hand),world(tip)

def body_shapes(f,clock):
    p,basis,right,left,hand,tip,other,world,rotate=skeleton(f,clock)
    oriented=tuple(rotate(v) for v in basis)
    shapes=[('head','box',world((0,1.87,0)),oriented,(.19,.23,.19)),
            ('body','box',world((0,1.19,0)),oriented,(.35,.43,.23))]
    for root,end,sign in ((right,hand,1),(left,other,-1)):
        elbow=joint(root,end,add(mul(basis[0],sign),(0,-.6,0)),.36)
        shapes.extend((('arms','capsule',world(root),world(elbow),.085),('arms','capsule',world(elbow),world(end),.075)))
    hip_yaw=f.get('body_yaw',f['yaw'])+p[7]+p[6]*.25;hip_basis=axes(hip_yaw)
    speed=min(1,math.hypot(f.get('move_x',0),f.get('move_z',0))/4.4);gait=f.get('gait',0)
    travel=norm((f.get('move_x',0),0,f.get('move_z',0)))
    for sign in (-1,1):
        hip=local((sign*.16,.86,0),hip_basis)
        step,lift=foot_step(gait,speed,sign)
        ankle=add(local((sign*.19,.12+lift,p[8]*(1 if sign==1 else -.4)),hip_basis),mul(travel,step))
        knee=joint(hip,ankle,hip_basis[2],.44)
        shapes.extend((('legs','capsule',world(hip),world(knee),.105),('legs','capsule',world(knee),world(ankle),.095)))
    shield=('shield','box',world(add(other,mul(basis[2],.10))),oriented,(.275,.375,.10)) if f.get('shield') and f.get('block') else None
    return shapes,shield

def segment_box(a,b,centre,basis,half,radius=0):
    start=sub(a,centre);delta=sub(b,a);lo,hi=0.,1.
    for axis,size in zip(basis,half):
        origin=dot(start,axis);direction=dot(delta,axis);extent=size+radius
        if abs(direction)<1e-10:
            if abs(origin)>extent:return None
        else:
            t0,t1=(-extent-origin)/direction,(extent-origin)/direction
            if t0>t1:t0,t1=t1,t0
            lo=max(lo,t0);hi=min(hi,t1)
            if lo>hi:return None
    return lo

def closest_segments(a,b,c,d):
    u,v,w=sub(b,a),sub(d,c),sub(a,c);uu,vv=dot(u,u),dot(v,v)
    uv,uw,vw=dot(u,v),dot(u,w),dot(v,w)
    if uu<1e-12:s=0.;t=clamp(vw/vv,0,1) if vv>1e-12 else 0.
    elif vv<1e-12:t=0.;s=clamp(-uw/uu,0,1)
    else:
        den=uu*vv-uv*uv;s=clamp((uv*vw-uw*vv)/den,0,1) if den>1e-12 else 0.
        t=(uv*s+vw)/vv
        if t<0:t=0.;s=clamp(-uw/uu,0,1)
        elif t>1:t=1.;s=clamp((uv-uw)/uu,0,1)
    delta=sub(add(a,mul(u,s)),add(c,mul(v,t)))
    return dot(delta,delta),s,t

def segment_capsule(a,b,c,d,radius):
    distance,t,_=closest_segments(a,b,c,d)
    if distance>radius*radius:return None
    length=math.sqrt(dot(sub(b,a),sub(b,a)))
    return max(0,t-math.sqrt(max(0,radius*radius-distance))/max(length,.00001))

def shape_hit(a,b,shape,radius=.055):
    if shape[1]=='box':return segment_box(a,b,*shape[2:],radius)
    return segment_capsule(a,b,shape[2],shape[3],shape[4]+radius)

def body_hit(a,b,shapes,radius=.055):
    hits=[(t,s[0]) for s in shapes if (t:=shape_hit(a,b,s,radius)) is not None]
    if not hits:return None
    t,zone=min(hits);return t,zone,add(a,mul(sub(b,a),t))

def active_window(f):
    if f.get('build_mode') and f.get('mine_progress',0)>0:
        move=DATA['moves']['overhead'];samples=move['aims']['legs'];position=((clock-f.get('mining_started',clock))%.85)/.85*DATA['intervals'];index=min(len(samples)-2,int(position));result=list(mix(samples[index],samples[index+1],position-index));result[3:6]=norm(result[3:6]);return result
    move=DATA['moves'].get(f.get('attack',''))
    if not move or f.get('attack')=='feint':return 0.,0.
    windup=f.get('attack_windup',move['windup']);duration=f.get('attack_duration',move['duration'])
    return windup*.72,windup+(duration-windup)*.32

def guard_direction(attack):
    return {'left':'right','right':'left','overhead':'up','thrust':'centre','disarm':'centre','rising':'centre','pommel':'centre','spin':'right','reverse_spin':'left'}.get(attack,'centre')

def debug_actor(f,clock):
    shapes,shield=body_shapes(f,clock)
    return dict(id=f['id'],shapes=shapes+([shield] if shield else []),blade=weapon_segment(f,clock),blocking=f['block'])
