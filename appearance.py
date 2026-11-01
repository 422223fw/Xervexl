"""Validated account cosmetics. Appearance never changes combat dimensions/stats."""
import copy
import math

DEFAULT_APPEARANCE=dict(skin=[.69,.49,.34],hair=[.19,.15,.11],cloth=[.21,.34,.32],trousers=[.18,.18,.16],accent=[.91,.64,.29],
                        tunic_pattern='plain',hair_style='cropped',cape=dict(style='none',colour=[.25,.12,.16],trim=[.91,.64,.29],pattern='plain',length=1.15))
CAPE_STYLES=('none','short','long','split')
PATTERNS=('plain','stripe','chevron','sun')

def validate_appearance(value,base=None):
    result=copy.deepcopy(base or DEFAULT_APPEARANCE)
    if not isinstance(value,dict) or set(value)-set(DEFAULT_APPEARANCE):raise ValueError('Choose valid skin and cape settings.')
    def colour(v):
        if not isinstance(v,list) or len(v)!=3 or any(type(n) not in (int,float) or not math.isfinite(n) or not 0<=n<=1 for n in v):raise ValueError('Colours must have three values between 0 and 1.')
        return [round(float(n),4) for n in v]
    for key in ('skin','hair','cloth','trousers','accent'):
        if key in value:result[key]=colour(value[key])
    for key,choices in (('tunic_pattern',PATTERNS),('hair_style',('cropped','crest','bald'))):
        if key in value:
            if value[key] not in choices:raise ValueError('Choose an available appearance style.')
            result[key]=value[key]
    if 'cape' in value:
        cape=value['cape']
        if not isinstance(cape,dict) or set(cape)-set(DEFAULT_APPEARANCE['cape']):raise ValueError('Choose valid cape settings.')
        for key in ('colour','trim'):
            if key in cape:result['cape'][key]=colour(cape[key])
        for key,choices in (('style',CAPE_STYLES),('pattern',PATTERNS)):
            if key in cape:
                if cape[key] not in choices:raise ValueError('Choose an available cape style.')
                result['cape'][key]=cape[key]
        if 'length' in cape:
            length=cape['length']
            if type(length) not in (int,float) or not math.isfinite(length) or not .6<=length<=1.35:raise ValueError('Cape length must be between 0.6 and 1.35 metres.')
            result['cape']['length']=round(float(length),3)
    return result

class Appearance:
    def appearance_for(self,user):return copy.deepcopy(user.get('appearance',DEFAULT_APPEARANCE))

    def save_appearance(self,s,body):
        u=s['user'];appearance=validate_appearance(body.get('appearance'),self.appearance_for(u))
        previous=copy.deepcopy(u.get('appearance'));u['appearance']=appearance
        try:self.save()
        except OSError:
            if previous is None:u.pop('appearance',None)
            else:u['appearance']=previous
            raise
        for session in self.sessions.values():
            if session['user'] is u and session['fighter'] in self.fighters:self.fighters[session['fighter']]['appearance']=copy.deepcopy(appearance)
        return dict(profile=self.session_profile(s),message='Your skin and cape are saved.')
