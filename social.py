"""Account-only friend requests and mutual friendships, stored privately."""
import json
import os
import time
import copy


def atomic_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp')
    with temporary.open('w',encoding='utf-8') as stream:
        json.dump(value,stream,ensure_ascii=False,separators=(',',':'));stream.flush();os.fsync(stream.fileno())
    for attempt in range(7):
        try:temporary.replace(path);return
        except PermissionError:
            if attempt==6:raise
            time.sleep(.02*(attempt+1))


class Social:
    def persist_social(self,previous):
        try:atomic_json(self.social_path,self.social)
        except OSError:self.social=previous;raise

    def setup_social(self):
        self.social_path=self.path.with_name(self.path.stem+'.social.json')
        self.social=json.loads(self.social_path.read_text('utf-8')) if self.social_path.exists() else dict(friends=[],requests=[])

    def friends_with(self,first,second):return sorted((first.lower(),second.lower())) in self.social['friends']

    def friend_name(self,name):
        if not isinstance(name,str) or name.lower() not in self.users:raise ValueError('Choose a registered player. Bots cannot receive friend requests.')
        return name.lower()

    def social_status(self,s):
        me=s['user']['username'].lower()
        def entry(name):
            online=[f for f in self.fighters.values() if not f['bot'] and f['name'].lower()==name and not f.get('eliminated')]
            world=self.worlds[online[0]['world_id']] if online else {}
            realm=world.get('realm_id','') if online and self.realm_access(self.realms.get(world.get('realm_id')),me) else ''
            return dict(username=self.users[name]['username'],online=bool(online),realm_id=realm,world_name=world.get('name',''))
        friends=[entry(pair[1] if pair[0]==me else pair[0]) for pair in self.social['friends'] if me in pair and all(n in self.users for n in pair)]
        return dict(friends=friends,incoming=[entry(a) for a,b in self.social['requests'] if b==me and a in self.users],
                    outgoing=[entry(b) for a,b in self.social['requests'] if a==me and b in self.users])

    def social_request(self,s,body):
        me=s['user']['username'].lower();other=self.friend_name(body.get('username'))
        if me==other:raise ValueError('You cannot add yourself.')
        previous=copy.deepcopy(self.social)
        if not self.friends_with(me,other) and [me,other] not in self.social['requests']:
            if sum(me in pair for pair in self.social['requests'])>=128:raise ValueError('Resolve your pending requests first.')
            self.social['requests'].append([me,other]);self.persist_social(previous)
        return dict(social=self.social_status(s),message='Friend request sent.' if not self.friends_with(me,other) else 'Already friends.')

    def social_respond(self,s,body):
        me=s['user']['username'].lower();other=self.friend_name(body.get('username'));accept=body.get('accept')
        if type(accept) is not bool:raise ValueError('Choose accept or decline.')
        if [other,me] not in self.social['requests']:raise ValueError('No incoming request from that player.')
        previous=copy.deepcopy(self.social)
        self.social['requests']=[p for p in self.social['requests'] if p!=[other,me] and (not accept or p!=[me,other])]
        if accept and not self.friends_with(me,other):self.social['friends'].append(sorted((me,other)))
        self.persist_social(previous)
        return dict(social=self.social_status(s),message='Friend added.' if accept else 'Request declined.')

    def social_remove(self,s,body):
        me=s['user']['username'].lower();other=self.friend_name(body.get('username'))
        previous=copy.deepcopy(self.social)
        self.social['friends']=[p for p in self.social['friends'] if p!=sorted((me,other))]
        self.social['requests']=[p for p in self.social['requests'] if p not in ([me,other],[other,me])]
        self.persist_social(previous)
        return dict(social=self.social_status(s),message='Friend removed.')
