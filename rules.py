"""Shared authoritative progression, equipment and damage rules for Xervexl."""
import math
import sys
from functools import lru_cache

VERSION = "0.4.0"
PROGRESSION_VERSION = 1
# Authoritative XP can grow beyond the interpreter's default decimal digit limit.
if hasattr(sys,"set_int_max_str_digits"):sys.set_int_max_str_digits(0)

WEAPONS = [
    dict(id="fists",name="Bare hands",price=0,damage=5,reach=1.05,cooldown=.48,family="unarmed",hidden=True),
    dict(id="knife",name="Worn knife",price=0,damage=16,reach=1.65,cooldown=.34,family="blade"),
    dict(id="dagger",name="Steel dagger",price=140,damage=19,reach=1.8,cooldown=.30,family="blade"),
    dict(id="arming",name="Arming sword",price=180,damage=23,reach=2.45,cooldown=.52,family="blade"),
    dict(id="sabre",name="Cavalry sabre",price=420,damage=25,reach=2.65,cooldown=.46,family="blade"),
    dict(id="longsword",name="Steel longsword",price=720,damage=31,reach=3.05,cooldown=.68,family="blade"),
    dict(id="rapier",name="Duelist rapier",price=950,damage=27,reach=3.25,cooldown=.48,family="blade"),
    dict(id="greatsword",name="Greatsword",price=1100,damage=39,reach=3.5,cooldown=.88,family="blade"),
    dict(id="axe",name="War axe",price=850,damage=37,reach=2.2,cooldown=.81,family="axe"),
    dict(id="mace",name="Flanged mace",price=1350,damage=34,reach=2.25,cooldown=.72,family="mace",armour_pierce=.35),
    dict(id="spear",name="Ash spear",price=1600,damage=28,reach=4.2,cooldown=.70,family="spear"),
    dict(id="halberd",name="Steel halberd",price=2800,damage=42,reach=3.9,cooldown=1.05,family="axe"),
    dict(id="bow",name="Hunter bow",price=650,damage=24,reach=26,cooldown=.9,family="bow",speed=23,gravity=2.5),
    dict(id="longbow",name="Yew longbow",price=1900,damage=33,reach=35,cooldown=1.2,family="bow",speed=30,gravity=2.),
    dict(id="crossbow",name="Steel crossbow",price=2600,damage=41,reach=38,cooldown=1.65,family="crossbow",speed=38,gravity=1.2),
    dict(id="slingshot",name="Leather slingshot",price=380,damage=17,reach=18,cooldown=.62,family="slingshot",speed=19,gravity=3.),
    dict(id="stormblade",name="Stormblade",price=12000,damage=43,reach=3.2,cooldown=.66,family="blade",magic="lightning"),
    dict(id="frostsabre",name="Frost sabre",price=16000,damage=38,reach=2.8,cooldown=.50,family="blade",magic="frost"),
    dict(id="emberstaff",name="Ember staff",price=22000,damage=32,reach=30,cooldown=1.1,family="staff",speed=21,gravity=0,magic="fire"),
    dict(id="moonbow",name="Moon bow",price=30000,damage=40,reach=42,cooldown=1.0,family="bow",speed=34,gravity=.8,magic="arcane"),
    dict(id="sunblade",name="Sunsteel sword",price=45000,damage=51,reach=3.4,cooldown=.85,family="blade",magic="fire"),
]
GEAR = [
    dict(id="woodshield",name="Wooden shield",price=120,kind="shield",reduction=.40),
    dict(id="buckler",name="Iron buckler",price=260,kind="shield",reduction=.58),
    dict(id="kite",name="Kite shield",price=580,kind="shield",reduction=.78),
    dict(id="tower",name="Tower shield",price=1800,kind="shield",reduction=.87,slow=.85),
    dict(id="runeshield",name="Runic shield",price=15000,kind="shield",reduction=.90),
    dict(id="leather",name="Leather armour",price=320,kind="armour",reduction=.12),
    dict(id="mail",name="Chainmail",price=680,kind="armour",reduction=.24),
    dict(id="plate",name="Steel cuirass",price=1200,kind="armour",reduction=.34,slow=.88),
    dict(id="brigandine",name="Brigandine",price=2800,kind="armour",reduction=.39,slow=.93),
    dict(id="runearmour",name="Runic armour",price=18000,kind="armour",reduction=.46,slow=.90),
    dict(id="ironhelm",name="Iron helmet",price=500,kind="helmet",reduction=.18),
    dict(id="steelhelm",name="Steel helmet",price=1800,kind="helmet",reduction=.32),
    dict(id="runehelm",name="Runic helmet",price=9000,kind="helmet",reduction=.42),
    dict(id="health",name="Permanent +20 health",price=12000,kind="upgrade",repeatable=True),
]
SPELLS = [
    dict(id="firebolt",name="Firebolt spell",price=8000,kind="spell",damage=28,speed=20,cooldown=3.,cost=25),
    dict(id="frostbolt",name="Frostbolt spell",price=10000,kind="spell",damage=20,speed=18,cooldown=4.,cost=25),
    dict(id="heal",name="Mending spell",price=16000,kind="spell",healing=25,cooldown=12.,cost=40),
    dict(id="ward",name="Ward spell",price=24000,kind="spell",absorb=25,cooldown=8.,cost=28),
    dict(id="shock",name="Shockwave spell",price=32000,kind="spell",damage=28,reach=4.5,cooldown=8.,cost=35),
]
WEAPONS += [
    dict(id="katana",name="Steel katana",price=2100,damage=29,reach=2.85,cooldown=.44,family="blade"),
    dict(id="falchion",name="Heavy falchion",price=1700,damage=35,reach=2.6,cooldown=.61,family="blade"),
    dict(id="estoc",name="Piercing estoc",price=3200,damage=30,reach=3.1,cooldown=.60,family="blade",armour_pierce=.3),
    dict(id="warhammer",name="War hammer",price=3500,damage=42,reach=2.1,cooldown=.95,family="mace",armour_pierce=.5),
    dict(id="grappling_rope",name="Grappling rope",price=2300,damage=0,reach=14,cooldown=2.3,family="rope"),
    dict(id="lasso",name="Combat lasso",price=4000,damage=0,reach=9,cooldown=2.,family="rope"),
]
GEAR += [dict(id="stability",name="Permanent footing",price=16000,kind="upgrade",repeatable=True)]
ITEMS = {i["id"]:i for i in WEAPONS+GEAR+SPELLS}
CATALOG = [i for i in WEAPONS+GEAR+SPELLS if not i.get("hidden")]
RANGED = {"bow","crossbow","slingshot","staff"}
TARGET_HEIGHTS = {"head":1.86,"body":1.25,"legs":.55}
BODY_MULTIPLIERS = {"head":1.45,"body":1.,"arms":.82,"legs":.68}
MOVES = {
    "left":dict(cost=12,windup=.18,follow=.28,multiplier=1.,reach=0.,arc=1.05),
    "right":dict(cost=12,windup=.18,follow=.28,multiplier=1.,reach=0.,arc=1.05),
    "overhead":dict(cost=20,windup=.26,follow=.32,multiplier=1.2,reach=0.,arc=.46),
    "thrust":dict(cost=12,windup=.18,follow=.26,multiplier=.85,reach=.35,arc=.30),
    "spin":dict(cost=30,windup=.36,follow=.44,multiplier=.82,reach=0.,arc=math.pi),
    "disarm":dict(cost=22,windup=.24,follow=.28,multiplier=0.,reach=0.,arc=.8),
}
PERSISTENT = ("xp","skill","coins","kills","deaths","parries","disarms","health_upgrades","stability_upgrades")


@lru_cache(maxsize=512)
def xp_for_level(level):
    """Cumulative XP: each rank costs the previous cost times the new rank."""
    total,cost=0,79
    for rank in range(2,max(1,int(level))+1):
        if rank>2:cost*=rank
        total+=cost
    return total


def level_for_xp(xp):
    xp=max(0,int(xp));rank,total,cost=1,0,79
    while xp>=total+cost:
        total+=cost;rank+=1;cost*=rank+1
    return rank


def public_integer(value):
    """Keep small JSON numbers; send larger integers as exact decimal strings."""
    return value if -(2**63)<=value<2**63 else str(value)


def migrate_progression(user):
    if user.get("progression_version",0)>=PROGRESSION_VERSION:return
    old=max(0,int(user.get("xp",0)))
    rank=max(1,(1+math.isqrt(1+4*old//75))//2)
    old_start=75*rank*(rank-1);old_span=150*rank
    start=xp_for_level(rank);span=xp_for_level(rank+1)-start
    user["xp"]=start+(old-old_start)*span//old_span
    user["progression_version"]=PROGRESSION_VERSION


def health_price(upgrades):
    return 12000*(1+upgrades)**2


def stability_price(upgrades):return 16000*(1+upgrades)**2


def complete_account(user):
    """Add fields without replacing the user's existing equipment or progress."""
    for key,value in dict(xp=0,skill=0,parries=0,disarms=0,health_upgrades=0,helmet="",spell="").items():
        user.setdefault(key,value)
    user.setdefault("stability_upgrades",0)
    user.setdefault("progression_version",PROGRESSION_VERSION)
    if "weapon_slots" not in user:
        equipped=user.get("weapon","knife")
        owned=[x for x in user.get("inventory",["knife"]) if x in ITEMS and ITEMS[x].get("kind","weapon")=="weapon" and not ITEMS[x].get("hidden")]
        slots=([equipped] if equipped in owned else [])+[x for x in owned if x!=equipped]
        user["weapon_slots"]=(slots[:5]+[""]*5)[:5]
    return user


def kill_reward(victim_level):
    return dict(xp=40+20*victim_level,skill=victim_level,coins=35+10*victim_level)


def death_penalty(victim_level,killer_level):
    return 2*victim_level+4*max(0,victim_level-killer_level)


def zone_from_height(height):
    return "head" if height>=1.65 else "legs" if height<.85 else "body"
