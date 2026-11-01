"""One additional, server-sequenced melee combination at every rank after 1."""
from rules import ITEMS,MOVES

AUTHORED=(
    ('Needle trick',('feint','thrust')),
    ('Crossing steel',('left','rising')),
    ('Close riposte',('pommel','right','thrust')),
    ('High-low cut',('overhead','left')),
    ('Turning tide',('left','spin')),
    ('Returning edge',('right','reverse_spin')),
    ('Rising storm',('rising','overhead','thrust')),
    ('Broken rhythm',('feint','left','pommel')),
    ('Duelist finish',('right','rising','thrust')),
)
ALPHABET=('left','right','overhead','thrust','rising','pommel','spin','reverse_spin')

def technique(rank):
    if type(rank) is not int or rank<2:raise ValueError('Techniques start at rank 2.')
    if rank<=len(AUTHORED)+1:name,moves=AUTHORED[rank-2]
    else:
        # Canonical base-eight digits produce a different combination at every
        # further rank; no finite unlock cap or random duplicate rolls.
        value=rank-len(AUTHORED)-2;digits=[]
        while True:
            digits.append(ALPHABET[value%len(ALPHABET)]);value//=len(ALPHABET)
            if not value:break
        moves=('rising','feint',*reversed(digits),'thrust');name='Steel form '+str(rank)
    return dict(rank=rank,name=name,moves=list(moves),stamina=sum(MOVES[m]['cost'] for m in moves))

class Techniques:
    def cancel_technique(self,f):
        f.update(technique_rank=0,technique_steps=[],technique_index=0)
        if f.pop('technique_queued',False):f['queued_attack']=''

    def technique_state(self,f):
        rank=f.get('technique_rank',0)
        return dict(rank=rank,name=technique(rank)['name'],step=f.get('technique_index',0),total=len(f['technique_steps'])) if rank else {}

    def technique_profile(self,u,level):
        selected=u.get('selected_technique',2 if level>=2 else 0)
        if type(selected) is not int or not 2<=selected<=level:selected=2 if level>=2 else 0
        return dict(technique_count=max(0,level-1),selected_technique=selected,next_technique=technique(level+1))

    def technique_catalog(self,s,body):
        p=self.session_profile(s);level=p['level'];page=body.get('page',0)
        if type(page) is not int or page<0:raise ValueError('Choose a valid technique page.')
        pages=max(1,(level+3+7)//8);page=min(page,pages-1)
        rows=[dict(technique(rank),unlocked=rank<=level,selected=rank==p['selected_technique']) for rank in range(2+page*8,min(level+5,2+(page+1)*8))]
        return dict(profile=p,techniques=dict(page=page,pages=pages,items=rows))

    def select_technique(self,s,body):
        rank=body.get('rank');level=self.session_profile(s)['level']
        if type(rank) is not int or not 2<=rank<=level:raise ValueError('Reach that rank to unlock this technique.')
        u=s['user'];previous=u.get('selected_technique');u['selected_technique']=rank
        try:self.save()
        except OSError:
            if previous is None:u.pop('selected_technique',None)
            else:u['selected_technique']=previous
            raise
        return dict(profile=self.session_profile(s),message='Selected '+technique(rank)['name']+'. Press O in combat.')

    def queue_technique(self,f,inp):
        requested=inp.get('technique_rank',0);pressed=bool(requested)
        rising=pressed and not f.get('last_technique',False);f['last_technique']=pressed
        unavailable=(f['dead']>0 or f.get('downed',0)>0 or f.get('eliminated') or f['fall']>0 or f['disarmed']>0 or f['block'] or f['dodge']>0 or inp.get('build_mode') or inp.get('drop') or ITEMS[f['weapon']]['family'] not in ('blade','axe','mace','spear','unarmed'))
        if unavailable or inp.get('attack'):
            if inp.get('attack'):f.pop('technique_queued',False)
            self.cancel_technique(f);return
        if rising and type(requested) is int and 2<=requested<=f['level'] and ITEMS[f['weapon']]['family'] in ('blade','axe','mace','spear','unarmed'):
            if not f.get('technique_rank'):
                f.update(technique_rank=requested,technique_steps=technique(requested)['moves'],technique_index=0)
        if not f.get('technique_rank'):return
        index=f['technique_index'];steps=f['technique_steps']
        if index>=len(steps):
            if f['cooldown']<=0:self.cancel_technique(f)
        elif f['cooldown']<=.20:
            f.update(queued_attack=steps[index],queued_until=self.clock+.25,queued_repeat=False,queued_auto_cut=False,technique_queued=True)

    def technique_attack_started(self,f,attack):
        if f.pop('technique_queued',False):
            i=f['technique_index']
            if i<len(f['technique_steps']) and attack==f['technique_steps'][i]:f['technique_index']+=1
