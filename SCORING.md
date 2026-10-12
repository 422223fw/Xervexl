# Xervexl 0.2 — progression and combat rules

Implemented on the authoritative server in `rules.py`, `combat.py` and `server.py`. Clients cannot submit XP, skill, crowns, rank, health upgrades or hit rewards.

| Event | XP gained | Skill points | Crowns |
|---|---:|---:|---:|
| Eliminate rank L opponent | 40 + 20 × L | +L | 35 + 10 × L |
| Perfect melee parry versus rank L | 15 + 5 × L | +max(1, floor(L / 3)) | 0 |
| Deflect arrow from rank L shooter | 12 + 5 × L | +max(1, floor(L / 3)) | 0 |
| Disarm rank L opponent | 25 + 10 × L | +max(1, floor(L / 2)) | 0 |
| Your weapon is knocked away at rank L | 0 | −(2 + L) | 0 |
| Voluntarily drop your weapon | 0 | 0 | 0 |

If you die at rank V to a rank K opponent, the skill penalty is **2 × V + 4 × max(0, V − K)**. For a rank 10 victim, losing to rank 10 costs 20 skill; losing to rank 1 costs 56. Skill floors at zero; XP and earned rank are not taken away on death. The HUD reports actual skill lost, which can be below the nominal penalty when you have few skill points.

Rank L begins at **75 × L × (L − 1) total XP**: rank 1 = 0, rank 2 = 150, rank 3 = 450, rank 4 = 900. Rank is separate from skill and spendable crowns. Bots receive shuffled AI depths 2–5 and randomized starting ranks, then gain XP and lose skill under the same combat rules. Bot progress lasts for their current server life; registered accounts persist across server restarts.

Leaderboards cover skill, rank, XP, current crowns and eliminations. They include registered accounts on this server and active combatants, with BOT/PLAYER labels. They do not aggregate independent internet servers. Guests who have not entered the arena are not persistent leaderboard entries.

## Combat

- **Perfect parry:** face the attack and start blocking within 180 ms of impact. It costs zero stamina, staggers the attacker and awards XP/skill. Holding guard beyond this window drains stamina on absorbed hits. Empty hands cannot parry. A perfect parry can disarm an attacker with less than 20 stamina.
- **Q disarm:** a deliberate windup costing 22 stamina. The victim must be exhausted (under 35 stamina) or recovering with their guard down. Failure awards nothing. Empty hands cannot be disarmed repeatedly.
- **G drop / F pickup:** actual shared world weapons fall briefly and expire after 25 seconds. Picking up a borrowed weapon does not grant permanent ownership. Your purchased loadout returns after death. Being disarmed briefly staggers you before recovery.
- **Z / X / C:** aim at legs, body or head. Damage multipliers are 0.68 / 1.0 / 1.45. Actual impact height also depends on jumping and projectile travel. Helmets protect head hits; armour protects other regions. Move and weapon damage also matter. Each direct damage event is capped at 75, so a fresh fighter with at least 100 health cannot be killed by a single direct hit.
- **Bows, crossbows, slingshots:** server-simulated speed, gravity, travel time and swept collisions. Shields absorb some projectile damage. Facing an arrow with a timed blade parry or active weapon swing can reflect it. Ownership changes: subsequent damage and kill rewards belong to the defender. At most two reflections per projectile prevent endless ping-pong.
- **Stamina:** attacks, dodges, jumps and spells consume it. Normal guard hits drain it. Regeneration is 18/sec normally and 8/sec while guarding. Perfect defence consumes none.
- **Magic:** Stormblade drains additional enemy stamina and delays recovery; Frost Sabre/Frostbolt slow real movement; fire weapons/Firebolt apply short burning damage. Healing, a temporary ward and a short shockwave are purchasable spells. Casting has server-controlled stamina costs and cooldowns. Players must buy and equip spells before use.

## Store

There are **39 visible items** across melee, ranged, armour/shields/helmets, arcane weapons/spells, and health. Prices and stats come from the server catalog. Arcane weapons cost 12,000–45,000 crowns and spells cost 8,000–32,000.

Each permanent upgrade adds **20 maximum health** and costs **12,000 × (existing upgrades + 1)²** crowns: 12,000, 48,000, then 108,000. It persists on respawn and adds only the new 20 health immediately to a living fighter. It is not a cheap full heal. Upgrades do not grant XP or skill. Crowns are game currency; purchases never use real money. Combat rewards cannot undo money spent in the store.

## חשבון הניקוד בקצרה

הריגה נותנת נקודות מיומנות בגובה דרגת היריב, ועוד XP וכסף לפי הדרגה. מוות ליריב בדרגה נמוכה יותר מוריד יותר נקודות מיומנות. XP ודרגות לא נמחקים במוות; נקודות מיומנות נעצרות באפס. עצירה מתוזמנת לא צורכת סיבולת ונותנת XP ונקודות, וכך גם פריקת נשק והחזרת חץ. נשק שנאסף מהזירה נשאר זמני ואינו נחשב רכישה בחנות.
