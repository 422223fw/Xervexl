"""Xervexl authoritative arena server. Python stdlib only; no administrator rights.

Bind to loopback by default. Put an HTTPS reverse proxy in front of a public server.
Account JSON is private runtime data, deliberately excluded from Git.
"""
import argparse
import hashlib
import hmac
import json
import math
import os
import random
import re
import secrets
import smtplib
import shutil
import threading
import time
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from rules import (VERSION,WEAPONS,GEAR,CATALOG,ITEMS,RANGED,PERSISTENT,
                   complete_account,level_for_xp,xp_for_level,health_price,stability_price)
from combat import Combat
from arena_features import ArenaFeatures

ROOT = Path(__file__).resolve().parent
BOT_NAMES = ["Ash", "Bram", "Cinder", "Dusk", "Flint", "Gale", "Hawke", "Ivar", "Juno", "Kestrel", "Lark", "Morrow"]


def clamp(v, a, b):
    return max(a, min(b, v))


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ":" + hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 310_000).hex()


def password_matches(password, stored):
    return hmac.compare_digest(password_hash(password, stored.split(":")[0]), stored)


class Arena(ArenaFeatures,Combat):
    def __init__(self, data_path=None, seed=None):
        self.path = Path(data_path or ROOT / "data" / "accounts.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.rng = random.Random(seed)
        self.lock = threading.RLock()
        self.users = json.loads(self.path.read_text("utf-8")) if self.path.exists() else {}
        if any("xp" not in u or "health_upgrades" not in u or "weapon_slots" not in u or "stability_upgrades" not in u for u in self.users.values()):
            shutil.copy2(self.path,self.path.with_name(self.path.stem+f".pre-progression-{time.time_ns()}.bak"))
            for u in self.users.values(): complete_account(u)
            self.save()
        if not self.path.exists(): self.save()
        self.sessions = {}
        self.resets = {}
        self.fighters = {}
        self.events = []
        self.event_serial = 0
        self.drops = []
        self.projectiles = []
        self.clock = 0.
        self.running = True
        self.bot_serial = 0
        self.bot_depths = [2,3,4,5]
        self.rng.shuffle(self.bot_depths)
        self.setup_worlds(seed)
        self.maintain_bots()

    def save(self):
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.users, indent=2), "utf-8")
        temporary.replace(self.path)

    def profile(self, user):
        level=level_for_xp(user["xp"])
        return dict({k:user[k] for k in ("username","inventory","weapon","weapon_slots","shield","armour","helmet","spell",*PERSISTENT)},
                    level=level,max_hp=100+20*user["health_upgrades"],next_level_xp=xp_for_level(level+1),
                    level_start_xp=xp_for_level(level),health_upgrade_price=health_price(user["health_upgrades"]),
                    stability_upgrade_price=stability_price(user["stability_upgrades"]),fall_resistance=1-.4**user["stability_upgrades"],guest=not bool(user["password"]))

    def account(self, name, email="", password=""):
        return complete_account(dict(username=name, email=email.lower(), password=password_hash(password) if password else "",
                    coins=100, inventory=["knife"], weapon="knife", shield="", armour="", kills=0, deaths=0))

    def session(self, user, guest=False):
        token = secrets.token_urlsafe(32)
        self.sessions[token] = dict(user=user, guest=guest, touched=time.monotonic(), fighter="")
        return dict(token=token, profile=self.profile(user),catalog=CATALOG)

    def spawn(self, identifier, name, bot=False, depth=0):
        angle = self.rng.random() * math.tau
        radius = self.rng.uniform(7, 16)
        f = dict(id=identifier, name=name, bot=bot, depth=depth, x=math.sin(angle)*radius, z=math.cos(angle)*radius,
                 yaw=angle+math.pi, hp=100., stamina=100., weapon="knife", shield="", armour="", kills=0, deaths=0,
                 cooldown=0., windup=0., attack="", attack_id=0, block=False, block_since=-999., jump=0., dodge=0., dead=0., spawn_safe=1.5,
                 input={}, last_input=0., last_attack=False, last_dodge=False, last_jump=False, plan_at=0., action="advance")
        f.update(xp=0,level=1,skill=0,coins=100,parries=0,disarms=0,health_upgrades=0,max_hp=100.,helmet="",spell="",
                 spell_cd=0.,ward=0.,ward_time=0.,slow=0.,disarmed=0.,aim_zone="body",aim_pitch=0.,
                 burn=0.,burn_tick=0.,burn_source="",
                 last_drop=False,last_pickup=False,last_cast=False)
        f.update(world_id=self.default_world,stability_upgrades=0,balance=100.,fall=0.,fall_duration=1.25,
                 guard_dir="centre",body_yaw=f["yaw"],move_x=0.,move_z=0.,gait=0.,attack_started=0.,attack_duration=.5)
        if bot:
            f["weapon"] = self.rng.choice(["knife", "arming", "sabre", "longsword"])
            if depth >= 4:
                f["armour"] = "leather"
                f["shield"] = "buckler"
            starting_level=self.rng.randint(max(1,(depth-2)*3+1),depth*3+2)
            f["xp"]=xp_for_level(starting_level);f["level"]=starting_level;f["skill"]=starting_level*3
            f["coins"]=starting_level*70
            if identifier.endswith("3"):f["weapon"]="bow"
            if identifier.endswith("6"):f["weapon"]="slingshot"
            if identifier.endswith("9"):f["weapon"]="crossbow"
            if depth==5 and self.rng.random()<.35:f["weapon"]="stormblade"
            if depth==5 and self.rng.random()<.25:f["spell"]="heal"
        f["loadout_weapon"]=f["weapon"]
        self.fighters[identifier] = f
        return f

    def maintain_bots(self):
        active={f["world_id"] for f in self.fighters.values() if not f["bot"]} or {self.default_world}
        for f in list(self.fighters.values()):
            if f["bot"] and f["world_id"] not in active:del self.fighters[f["id"]]
        for world_id in active:
            humans=sum(not f["bot"] and f["world_id"]==world_id for f in self.fighters.values())
            wanted=max(0,10-humans);bots=[f for f in self.fighters.values() if f["bot"] and f["world_id"]==world_id]
            while len(bots)<wanted:
                self.bot_serial+=1
                f=self.spawn(f"bot-{self.bot_serial}",BOT_NAMES[(self.bot_serial-1)%len(BOT_NAMES)],True,self.bot_depths[(self.bot_serial-1)%4])
                f["world_id"]=world_id;bots.append(f)
            for f in bots[wanted:]:del self.fighters[f["id"]]

    def authenticate(self, token):
        s = self.sessions.get(token)
        if not s:
            raise ValueError("Please sign in again.")
        s["touched"] = time.monotonic()
        return s

    def join(self, s,world_id=None):
        if s["fighter"] in self.fighters:
            return s["fighter"]
        # One combatant per registered account, even across multiple sessions.
        if not s["guest"]:
            for other in self.sessions.values():
                if other is not s and other["user"] is s["user"] and other["fighter"] in self.fighters:
                    self.fighters.pop(other["fighter"], None)
                    other["fighter"] = ""
        pid = "p-" + secrets.token_hex(5)
        f = self.spawn(pid, s["user"]["username"])
        f["world_id"]=self.choose_world() if world_id is None else world_id
        for k in ("weapon","shield","armour","helmet","spell",*PERSISTENT):
            f[k] = s["user"][k]
        f.update(loadout_weapon=f["weapon"],level=level_for_xp(f["xp"]),max_hp=100+20*f["health_upgrades"])
        f["hp"]=f["max_hp"]
        s["fighter"] = pid
        self.maintain_bots()
        return pid

    def request(self, route, body, token=""):
        with self.lock:
            if route == "/health":
                return dict(ok=True,name="Xervexl",company="motlon",version=VERSION,mail_ready=bool(os.getenv("SMTP_HOST")),catalog=CATALOG,worlds=self.worlds)
            if route == "/auth/register":
                name = str(body.get("username", "")).strip()
                email = str(body.get("email", "")).strip().lower()
                password = str(body.get("password", ""))
                if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", name):
                    raise ValueError("Username: 3-20 letters, numbers or underscore.")
                if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
                    raise ValueError("Enter a valid email address.")
                if len(password) < 8 or len(password) > 128:
                    raise ValueError("Password: 8-128 characters.")
                if name.lower() in self.users or any(u["email"] == email for u in self.users.values()):
                    raise ValueError("Username or email is already registered.")
                user = self.account(name, email, password)
                self.users[name.lower()] = user
                self.save()
                return self.session(user)
            if route == "/auth/login":
                user = self.users.get(str(body.get("username", "")).lower())
                password = str(body.get("password", ""))[:128]
                # Equal-cost hashing also for unknown accounts.
                stored = user["password"] if user else "00"*16 + ":" + "00"*32
                valid = password_matches(password, stored)
                if not user or not valid:
                    raise ValueError("Username or password is incorrect.")
                return self.session(user)
            if route == "/auth/guest":
                return self.session(self.account("Guest-"+secrets.token_hex(2)), True)
            if route == "/auth/forgot":
                if not os.getenv("SMTP_HOST"):
                    raise ValueError("Email recovery is not configured on this server yet.")
                name = str(body.get("username", "")).lower()
                email = str(body.get("email", "")).strip().lower()
                user = self.users.get(name)
                if user and user["email"] == email:
                    code = secrets.token_urlsafe(24)
                    self.resets[hashlib.sha256(code.encode()).hexdigest()] = (name, time.monotonic()+900)
                    threading.Thread(target=self.send_reset, args=(email, code), daemon=True).start()
                return dict(message="If the username and email match, a reset code will be emailed.")
            if route == "/auth/reset":
                code_hash = hashlib.sha256(str(body.get("code", "")).encode()).hexdigest()
                entry = self.resets.get(code_hash)
                password = str(body.get("password", ""))
                if not entry or entry[1] < time.monotonic():
                    raise ValueError("Reset code is invalid or expired.")
                if not 8 <= len(password) <= 128:
                    raise ValueError("Password: 8-128 characters.")
                user = self.users[entry[0]]
                user["password"] = password_hash(password)
                self.resets.pop(code_hash)
                for key, s in list(self.sessions.items()):
                    if s["user"] is user:
                        self.fighters.pop(s["fighter"], None)
                        del self.sessions[key]
                self.maintain_bots()
                self.save()
                return dict(message="Password updated. Sign in with your new password.")
            s = self.authenticate(token)
            user = s["user"]
            if route=="/auth/logout":
                self.fighters.pop(s["fighter"],None);self.sessions.pop(token);self.maintain_bots()
                return dict(logged_out=True,message="Logged out. Your account progress is saved.")
            if route=="/inventory/assign":return self.inventory_assign(s,body.get("slot"),str(body.get("item","")))
            if route=="/inventory/switch":return self.inventory_switch(s,body.get("slot"))
            if route=="/arena/world":
                current=self.fighters.get(s["fighter"]);previous=current["world_id"] if current else None
                chosen=body.get("world_id",self.choose_world(previous))
                if not isinstance(chosen,int) or not 0<=chosen<len(self.worlds):raise ValueError("Unknown world.")
                self.fighters.pop(s["fighter"],None);s["fighter"]=""
                pid=self.join(s,chosen)
                return dict(player=pid,profile=self.profile(user),world=self.worlds[chosen])
            if route == "/me":
                return dict(profile=self.profile(user), catalog=CATALOG)
            if route == "/leaderboards":
                return dict(leaderboards=self.leaderboards(),profile=self.profile(user))
            if route in ("/shop/buy", "/shop/equip"):
                item_id = str(body.get("item", ""))
                if item_id not in ITEMS or ITEMS[item_id].get("hidden"):
                    raise ValueError("Unknown item.")
                item = ITEMS[item_id]
                if item_id=="stability":
                    if route!="/shop/buy":raise ValueError("Footing upgrades are purchased.")
                    price=stability_price(user["stability_upgrades"])
                    if user["coins"]<price:raise ValueError(f"Footing upgrade costs {price} crowns.")
                    user["coins"]-=price;user["stability_upgrades"]+=1
                    fighter=self.fighters.get(s["fighter"])
                    if fighter:fighter.update(coins=user["coins"],stability_upgrades=user["stability_upgrades"])
                    if not s["guest"]:self.save()
                    return dict(profile=self.profile(user),message="Footing improved: significantly lower knockdown risk.")
                if item_id=="health":
                    if route!="/shop/buy":raise ValueError("Health upgrades are purchased, not equipped.")
                    price=health_price(user["health_upgrades"])
                    if user["coins"]<price:raise ValueError(f"Permanent health costs {price} crowns.")
                    user["coins"]-=price;user["health_upgrades"]+=1
                    fighter=self.fighters.get(s["fighter"])
                    if fighter:
                        fighter["coins"]=user["coins"];fighter["health_upgrades"]=user["health_upgrades"]
                        fighter["max_hp"]=100+20*user["health_upgrades"]
                        if fighter["dead"]<=0:fighter["hp"]=min(fighter["max_hp"],fighter["hp"]+20)
                    if not s["guest"]:self.save()
                    return dict(profile=self.profile(user),message="Maximum health increased by 20.")
                if route == "/shop/buy" and item_id not in user["inventory"]:
                    if user["coins"] < item["price"]:
                        raise ValueError("Not enough crowns. Earn crowns in the arena.")
                    user["coins"] -= item["price"]
                    user["inventory"].append(item_id)
                if item_id not in user["inventory"]:
                    raise ValueError("You do not own that item.")
                kind = item.get("kind", "weapon")
                user[kind] = item_id
                if kind=="weapon" and item_id not in user["weapon_slots"] and "" in user["weapon_slots"]:
                    user["weapon_slots"][user["weapon_slots"].index("")]=item_id
                if s["fighter"] in self.fighters:
                    fighter=self.fighters[s["fighter"]]
                    fighter[kind]=item_id;fighter["coins"]=user["coins"]
                    if kind=="weapon":fighter["loadout_weapon"]=item_id
                if not s["guest"]:
                    self.save()
                return dict(profile=self.profile(user))
            if route == "/arena/join":
                return dict(player=self.join(s), profile=self.profile(user))
            if route == "/arena/leave":
                self.fighters.pop(s["fighter"], None)
                s["fighter"] = ""
                self.maintain_bots()
                return dict(ok=True)
            if route == "/arena/state":
                f = self.fighters.get(s["fighter"])
                if f:
                    # Positions, damage and rewards are NEVER accepted from the client.
                    movement = body.get("move", [0, 0])
                    if not isinstance(movement,(list,tuple)) or len(movement)!=2:
                        raise ValueError("Invalid movement.")
                    try:
                        mx, mz = float(movement[0]), float(movement[1])
                        yaw = float(body.get("yaw", f["yaw"]))
                        if not all(math.isfinite(v) for v in (mx, mz, yaw)):
                            raise ValueError()
                    except (ValueError, TypeError, IndexError):
                        raise ValueError("Invalid movement.")
                    f["input"] = dict(move=[clamp(mx,-1,1), clamp(mz,-1,1)], yaw=wrap(yaw),
                                      attack=body.get("attack", "") if body.get("attack", "") in ("left","right","overhead","thrust","disarm") else "",
                                      block=bool(body.get("block")),dodge=bool(body.get("dodge")),jump=bool(body.get("jump")),
                                      drop=bool(body.get("drop")),pickup=bool(body.get("pickup")),cast=bool(body.get("cast")),
                                      aim_zone=body.get("aim_zone") if body.get("aim_zone") in ("head","body","legs") else "body")
                    f["input"]["guard_dir"]=body.get("guard_dir") if body.get("guard_dir") in ("left","right","up","centre") else "centre"
                    try:
                        pitch=float(body.get("aim_pitch",0))
                        if not math.isfinite(pitch):raise ValueError()
                    except (TypeError,ValueError):raise ValueError("Invalid aim.")
                    f["input"]["aim_pitch"]=clamp(pitch,-.8,.8)
                    f["last_input"] = self.clock
                public = []
                room=f["world_id"] if f else self.default_world
                for a in self.fighters.values():
                    if a["world_id"]!=room:continue
                    public.append({k:a[k] for k in ("id","name","bot","depth","x","z","yaw","hp","max_hp","stamina","weapon","shield","armour","helmet","spell","kills","deaths","block","jump","dodge","dead","attack","attack_id","windup","spawn_safe","level","xp","skill","coins","disarmed","spell_cd","ward","slow","cooldown","world_id","body_yaw","move_x","move_z","gait","guard_dir","attack_started","attack_duration","balance","fall","fall_duration")})
                return dict(player=s["fighter"], time=self.clock, fighters=public, events=[e for e in self.events if e.get("world_id",room)==room][-12:],
                            profile=self.profile(user),humans=sum(not a["bot"] for a in public),bots=sum(a["bot"] for a in public),
                            drops=[d for d in self.drops if d["world_id"]==room],projectiles=[p for p in self.projectiles if p["world_id"]==room],
                            ropes=[r for r in self.ropes if r["world_id"]==room],world=self.worlds[room])
            raise ValueError("Unknown endpoint.")

    def send_reset(self, email, code):
        try:
            msg = EmailMessage()
            msg["From"] = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", ""))
            msg["To"] = email
            msg["Subject"] = "Xervexl password reset"
            msg.set_content(f"Your one-use reset code is:\n\n{code}\n\nIt expires in 15 minutes. If you did not request it, ignore this message.")
            with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587")), timeout=15) as smtp:
                smtp.starttls()
                if os.getenv("SMTP_USER"):
                    smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
                smtp.send_message(msg)
        except Exception:
            print("Password recovery email could not be delivered. Check SMTP configuration.", flush=True)

    def plan_bot(self, bot, opponent):
        """Actual depth 2..5 adversarial beam search over a simplified combat model.

        Each ply forecasts approach/retreat, attacks, blocking and opponent replies.
        This deliberately bounded approximation does not solve optimal human play.
        """
        distance = math.hypot(opponent["x"]-bot["x"], opponent["z"]-bot["z"])
        own = ITEMS[bot["weapon"]]
        enemy = ITEMS[opponent["weapon"]]
        actions = ("advance", "retreat", "strafe_l", "strafe_r", "block", "left", "overhead", "thrust", "dodge")
        ranged=own["family"] in RANGED
        if ranged:actions=("advance","retreat","strafe_l","strafe_r","thrust","dodge")
        beam = [(0., distance, bot["hp"], opponent["hp"], bot["stamina"], "", bot["cooldown"], opponent["cooldown"])]
        threat = opponent["windup"] > 0 or bool(opponent["input"].get("attack"))
        for ply in range(bot["depth"]):
            next_beam = []
            for previous_score, dist, hp, ehp, stamina, first, cd, ecd in beam:
                for action in actions:
                    d, h, e, st = dist, hp, ehp, stamina
                    own_cd, enemy_cd = max(0.,cd-.25), max(0.,ecd-.25)
                    if action == "advance": d = max(.9,d-1.05)
                    if action == "retreat": d += .8
                    if action.startswith("strafe"): d += .12
                    if action == "dodge":
                        if st < 24: continue
                        st -= 24
                        d += .9
                    if action in ("left", "overhead", "thrust"):
                        cost = 20 if action == "overhead" else 12
                        if st < cost or own_cd > 0: continue
                        st -= cost
                        reach = own["reach"] + (.35 if action=="thrust" else 0)
                        if d < reach:
                            e -= own["damage"] * (1.2 if action == "overhead" else .85 if action == "thrust" else 1.) * (.45 if opponent["block"] else 1.)
                        own_cd = own["cooldown"] + (.18 if action == "overhead" else -.05 if action == "thrust" else 0)
                    # Best plausible reply: attack in range; otherwise close the gap.
                    if enemy_cd <= 0 and d < enemy["reach"] + .2:
                        incoming = enemy["damage"] * (1.4 if threat and ply == 0 else .55)
                        if action == "block" and bot["weapon"] != "fists":
                            incoming = 0.
                        elif action == "dodge": incoming *= .08
                        elif action.startswith("strafe"): incoming *= .65
                        h -= incoming
                        enemy_cd = enemy["cooldown"]
                    else: d = max(.8,d-.5)
                    st = min(100, st+4)
                    # Discount future gains so replanning does not endlessly defer attacks.
                    gain = (ehp-e)*1.45 - (hp-h)*1.15 + (dist-d)*1.5
                    if action == "block" and not threat: gain -= 2.
                    if action == "retreat" and bot["hp"]>35: gain -= 1.
                    preferred=10. if ranged else own["reach"]*.78
                    score = previous_score + gain*(.76**ply) - abs(d-preferred)*.25
                    if h <= 0: score -= 180
                    if e <= 0: score += 140
                    # Small stable preference prevents permanent block/retreat equilibria.
                    if action == "advance": score += .35*(.76**ply)
                    next_beam.append((score,d,h,e,st,first or action,own_cd,enemy_cd))
            next_beam.sort(key=lambda n:n[0], reverse=True)
            beam = next_beam[:7]
        return beam[0][5] if beam else "advance"

    def bot_input(self, f):
        local_drops=[d for d in self.drops if d["world_id"]==f["world_id"]]
        if f["weapon"]=="fists" and local_drops:
            drop=min(local_drops,key=lambda d:math.hypot(d["x"]-f["x"],d["z"]-f["z"]))
            yaw=math.atan2(drop["x"]-f["x"],drop["z"]-f["z"])
            return dict(move=[math.sin(yaw),math.cos(yaw)],yaw=yaw,pickup=True)
        enemies = [a for a in self.fighters.values() if a["id"] != f["id"] and a["dead"] <= 0 and self.same_world(f,a)]
        if not enemies:
            return {}
        target = min(enemies,key=lambda a:math.hypot(a["x"]-f["x"],a["z"]-f["z"]))
        if self.clock >= f["plan_at"]:
            f["action"] = self.plan_bot(f,target)
            f["plan_at"] = self.clock + .22 + (5-f["depth"])*.075
        yaw = math.atan2(target["x"]-f["x"],target["z"]-f["z"])
        action = f["action"]
        mx,mz = math.sin(yaw),math.cos(yaw)
        if action == "retreat": mx,mz = -mx,-mz
        elif action == "strafe_l": mx,mz = -mz,mx
        elif action == "strafe_r": mx,mz = mz,-mx
        elif action not in ("advance", "dodge"): mx,mz = 0,0
        attack = action if action in ("left","overhead","thrust") else ""
        if f["depth"]>=3 and target["weapon"]!="fists" and target["stamina"]<30 and math.hypot(target["x"]-f["x"],target["z"]-f["z"])<2.3:
            attack="disarm"
        # Repeated attacks are separated by a released input edge.
        if f["last_attack"]: attack = ""
        return dict(move=[mx,mz],yaw=yaw,attack=attack,block=action=="block",dodge=action=="dodge" and not f["last_dodge"],jump=False,
                    aim_zone="head" if f["depth"]>=4 else "body",cast=bool(f["spell"]) and f["hp"]<50,
                    guard_dir={"left":"right","right":"left","overhead":"up"}.get(target["attack"],"centre"))

    def tick(self, dt):
        with self.lock:
            self.clock += dt
            now = time.monotonic()
            for token,s in list(self.sessions.items()):
                if now-s["touched"] > 60:
                    self.fighters.pop(s["fighter"],None)
                    del self.sessions[token]
            self.maintain_bots()
            for f in list(self.fighters.values()):
                if f["dead"] > 0:
                    f["dead"] -= dt
                    if f["dead"] <= 0:
                        f["dead"] = 0
                        angle = self.rng.random()*math.tau
                        f.update(x=math.sin(angle)*18,z=math.cos(angle)*18,hp=f["max_hp"],stamina=100.,cooldown=0.,windup=0.,attack="",block=False,spawn_safe=1.5,
                                 weapon=f["loadout_weapon"],disarmed=0.,ward=0.,slow=0.,burn=0.,last_attack=False,fall=0.,balance=100.)
                    continue
                if f["bot"]: inp = self.bot_input(f)
                else: inp = f["input"] if self.clock-f["last_input"] < .5 else {}
                if f["burn"]>0:
                    f["burn"]=max(0.,f["burn"]-dt);f["burn_tick"]+=dt
                    if f["burn_tick"]>=.5:
                        f["burn_tick"]-=.5;source=self.fighters.get(f["burn_source"])
                        if source:self.damage(source,f,1.5,"body",kind="burn")
                    if f["dead"]>0:continue
                f["spawn_safe"] = max(0.,f["spawn_safe"]-dt)
                f["yaw"] = inp.get("yaw",f["yaw"])
                f["fall"]=max(0.,f["fall"]-dt);f["balance"]=min(100.,f["balance"]+dt*12)
                if f["fall"]>0:f["block"]=False;f["move_x"]=f["move_z"]=0.;continue
                f["aim_zone"]=inp.get("aim_zone","body");f["aim_pitch"]=inp.get("aim_pitch",0)
                for timer in ("spell_cd","slow","disarmed","ward_time"):f[timer]=max(0.,f[timer]-dt)
                if f["ward_time"]<=0:f["ward"]=0.
                if inp.get("drop") and not f["last_drop"]:self.drop_weapon(f)
                if inp.get("pickup") and not f["last_pickup"]:self.pickup_weapon(f)
                if inp.get("cast") and not f["last_cast"]:self.cast_spell(f)
                for action in ("drop","pickup","cast"):f["last_"+action]=bool(inp.get(action))
                if f["bot"]:f["last_pickup"]=False
                f["cooldown"] = max(0.,f["cooldown"]-dt)
                f["dodge"] = max(0.,f["dodge"]-dt)
                f["jump"] = max(0.,f["jump"]-dt)
                was_blocking = f["block"]
                old_guard=f["guard_dir"];f["guard_dir"]=inp.get("guard_dir","centre")
                f["block"] = bool(inp.get("block")) and f["disarmed"]<=0
                if f["block"]:
                    if f["windup"]>0 or f["attack"]:f["windup"]=0.;f["attack"]="";f["cooldown"]=min(f["cooldown"],.12)
                    if not was_blocking or old_guard!=f["guard_dir"]:f["block_since"]=self.clock
                if inp.get("dodge") and not f["last_dodge"] and f["stamina"] >= 24 and f["dodge"]<=0:
                    f["dodge"] = .32
                    f["stamina"] -= 24
                if inp.get("jump") and not f["last_jump"] and f["jump"]<=0 and f["stamina"] >= 8:
                    f["jump"] = .55
                    f["stamina"] -= 8
                f["last_dodge"] = bool(inp.get("dodge"))
                f["last_jump"] = bool(inp.get("jump"))
                move = inp.get("move",[0,0])
                length = max(1.,math.hypot(*move))
                speed = 4.4*(.62 if f["block"] else 1.)*(2.5 if f["dodge"]>0 else 1.)
                speed*=ITEMS.get(f["armour"],{}).get("slow",1.)*ITEMS.get(f["shield"],{}).get("slow",1.)
                if f["slow"]>0:speed*=.60
                f["x"] += move[0]/length*speed*dt
                f["z"] += move[1]/length*speed*dt
                f["move_x"]=move[0]/length*speed;f["move_z"]=move[1]/length*speed
                f["gait"]+=math.hypot(f["move_x"],f["move_z"])*dt*3.5
                desired_yaw=f["yaw"] if f["block"] or f["attack"] else math.atan2(move[0],move[1]) if math.hypot(*move)>.1 else f["body_yaw"]
                f["body_yaw"]+=wrap(desired_yaw-f["body_yaw"])*min(1.,dt*12)
                self.collision_props(f)
                radius = math.hypot(f["x"],f["z"])
                if radius > 38:
                    f["x"] *= 38/radius
                    f["z"] *= 38/radius
                f["stamina"] = min(100.,f["stamina"]+dt*(8 if f["block"] else 18))
                attack = inp.get("attack", "")
                ranged=ITEMS[f["weapon"]]["family"] in RANGED
                cost = 18 if ITEMS[f["weapon"]]["family"]=="rope" else 22 if attack=="disarm" else 10 if ranged else 20 if attack == "overhead" else 12
                if attack and not f["last_attack"] and f["cooldown"]<=0 and f["stamina"]>=cost and not f["block"] and f["disarmed"]<=0:
                    f["attack"] = attack
                    f["attack_id"] += 1
                    f["windup"] = .24 if attack=="disarm" else .22 if attack == "overhead" else .16
                    f["attack_started"]=self.clock;f["attack_duration"]=f["windup"]+.32
                    f["cooldown"] = ITEMS[f["weapon"]]["cooldown"] + (0 if ranged else .18 if attack == "overhead" else -.05 if attack == "thrust" else 0)
                    f["stamina"] -= cost
                f["last_attack"] = bool(attack)
                if f["windup"] > 0:
                    f["windup"] -= dt
                    if f["windup"] <= 0: self.strike(f)
                if f["cooldown"] <= 0: f["attack"] = ""
            alive = [f for f in self.fighters.values() if f["dead"]<=0]
            self.tick_objects(dt)
            self.tick_ropes(dt)
            for i,a in enumerate(alive):
                for b in alive[i+1:]:
                    if not self.same_world(a,b):continue
                    dx,dz = b["x"]-a["x"],b["z"]-a["z"]
                    dist = math.hypot(dx,dz)
                    if .001 < dist < .78:
                        push = (.78-dist)*.5
                        a["x"] -= dx/dist*push; a["z"] -= dz/dist*push
                        b["x"] += dx/dist*push; b["z"] += dz/dist*push

    def run(self):
        previous = time.monotonic()
        while self.running:
            current = time.monotonic()
            self.tick(min(.1,current-previous))
            previous = current
            time.sleep(1/30)


class Handler(BaseHTTPRequestHandler):
    arena = None
    limits = {}
    limits_lock = threading.Lock()

    def do_GET(self):
        self.handle_api({})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length",0))
            if length > 16384 or length < 0: raise ValueError("Request too large.")
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body,dict): raise ValueError("Expected an object.")
            self.handle_api(body)
        except (ValueError,json.JSONDecodeError):
            self.respond(400,dict(error="Invalid request."))

    def handle_api(self, body):
        try:
            if self.path.startswith("/auth/"):
                # Fixed window per source; isolates credential requests from arena polling.
                ip = self.client_address[0]
                with self.limits_lock:
                    count,start = self.limits.get(ip,(0,time.monotonic()))
                    if time.monotonic()-start > 60: count,start = 0,time.monotonic()
                    self.limits[ip] = (count+1,start)
                if count >= 30:
                    self.respond(429,dict(error="Too many account requests. Wait one minute.")); return
            token = self.headers.get("Authorization", "").removeprefix("Bearer ")
            self.respond(200,self.arena.request(self.path,body,token))
        except ValueError as error:
            self.respond(400,dict(error=str(error)))
        except Exception:
            self.respond(500,dict(error="Server error. Check server console."))

    def respond(self, status, value):
        encoded = json.dumps(value,separators=(",",":")).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(encoded)))
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        try: self.wfile.write(encoded)
        except (BrokenPipeError,ConnectionResetError): pass

    def log_message(self,*args):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--data",type=Path,default=ROOT/"data"/"accounts.json")
    args = parser.parse_args()
    Handler.arena = Arena(args.data)
    server = ThreadingHTTPServer((args.host,args.port),Handler)
    threading.Thread(target=Handler.arena.run,daemon=True).start()
    print(f"Xervexl / motlon — server at http://{args.host}:{args.port}",flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        Handler.arena.running = False
        server.server_close()


if __name__ == "__main__":
    main()
