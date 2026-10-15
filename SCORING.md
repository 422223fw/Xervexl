# Xervexl 0.8 — progression and combat rules

Official round victories grant **650 XP, 350 crowns and 25 skill** once per registered member of the winning round roster. Eliminated/disconnected squad members are included. Moving to another arena cannot erase the award on the next progress sync. Winning bots receive the same bonus for their current character. The endless arena keeps its existing kill/death economy and has no final winner.

The 100-fighter squad mode has 25 teams of four and disables friendly damage, disarm farming and hostile ropes between teammates. Lethal damage can down a fighter for 24 seconds; a teammate within 2.2 metres can channel a three-second revive to restore half health. Releasing, moving, attacking, blocking, taking damage or leaving range interrupts it. Several helpers do not shorten the channel. Finishing damage, bleeding out or losing the whole upright squad eliminates the fighter for the round. A living, upright killer retains the full-health/stamina refill; elimination does not automatically revive a dead/downed shooter.

Custom workshop modes are **unranked**. Their script scores, XP/crowns, temporary starting equipment and combat stat changes remain within the match and are excluded from persistent accounts and global leaderboards. Official mode rewards remain authoritative. See `WORKSHOP.md` for the supported event programming language.

Implemented on the authoritative server in `rules.py`, `combat.py`, `arena_features.py` and `server.py`. Clients cannot submit XP, skill, crowns, rank, upgrades or hit rewards. New accounts start at **rank 1, 0 XP, 0 skill points, 100 crowns and a knife**. Updating the game does not reset existing accounts.

| Event | XP gained | Skill points | Crowns |
|---|---:|---:|---:|
| Eliminate rank L opponent | 40 + 20 × L | +L | 35 + 10 × L |
| Perfect melee parry versus rank L | 15 + 5 × L | +max(1, floor(L / 3)) | 0 |
| Deflect arrow from rank L shooter | 12 + 5 × L | +max(1, floor(L / 3)) | 0 |
| Disarm rank L opponent | 25 + 10 × L | +max(1, floor(L / 2)) | 0 |
| Your weapon is knocked away at rank L | 0 | −(2 + L) | 0 |
| Voluntarily drop your weapon | 0 | 0 | 0 |

If you die at rank V to a rank K opponent, the skill penalty is **2 × V + 4 × max(0, V − K)**. For a rank 10 victim, losing to rank 10 costs 20 skill; losing to rank 1 costs 56. Skill floors at zero; XP and earned rank are not taken away on death. The HUD reports actual skill lost, which can be below the nominal penalty when you have few skill points.

Rank 2 requires **79 additional XP**. Every following rank costs the previous rank's cost multiplied by the new rank: 79, 237, 948, 4,740, 28,440, and so on. Rank is separate from skill and spendable crowns.

| Rank reached | Additional XP from previous rank | Cumulative XP |
|---|---:|---:|
| 1 | 0 | 0 |
| 2 | 79 | 79 |
| 3 | 237 | 316 |
| 4 | 948 | 1,264 |
| 5 | 4,740 | 6,004 |
| 6 | 28,440 | 34,444 |

For rank L ≥ 2, the additional cost is **79 × L! / 2**. Total XP is the sum of the costs through that rank. There is no configured maximum rank. Authoritative XP uses arbitrary-precision integers; huge public values travel as decimal strings and the native interface displays them in compact scientific notation. Existing accounts receive a one-time, backed-up conversion from the former 75 × L × (L − 1) curve that preserves earned rank and proportional progress, instead of dropping their ranks when the formula changes. Credentials, equipment, coins and skill are preserved. Bots receive shuffled AI depths 2–5 and randomized starting ranks, then gain XP and lose skill under the same combat rules. Bot progress lasts for their current server life; registered accounts persist across server restarts.

Every elimination immediately restores the living killer to **their full maximum health, including permanent health upgrades, and 100 stamina**. This applies to players and bots, including melee, ranged, magic, burning and reflected-arrow kills. Nonlethal hits do not restore either resource. A posthumous kill still earns its rewards but does not revive a dead shooter.

Leaderboards cover skill, rank, XP, current crowns and eliminations. They include registered accounts on this server and active combatants, with BOT/PLAYER labels. They do not aggregate independent internet servers. Playing requires a registered account; the old guest endpoint is disabled.

## Combat

- **Perfect parry:** face the attack tightly, match its direction and start/change guard within 180 ms of impact. It costs zero stamina, disarms the attacker regardless of their stamina, and awards both the parry and disarm rewards above. Match left cuts with right guard, right cuts with left guard, overheads with high guard, and thrusts with centre guard. Centre guard also covers horizontal cuts. Empty hands cannot parry. Holding an aligned guard absorbs melee damage with no stamina loss but no repeated XP reward. A mismatched guard provides only partial protection. Blocking cancels your ongoing attack immediately.
- **Q disarm:** a deliberate windup costing 22 stamina. The victim must be exhausted (under 35 stamina) or recovering with their guard down. Failure awards nothing. Empty hands cannot be disarmed repeatedly.
- **Cuts/thrust/spin:** left/right cuts cost 12 stamina and use an 180 ms windup, overhead costs 20 with 260 ms, direct thrust costs 12 with 180 ms. The optional R spinning cut costs 30, winds up for 360 ms and deals 82% weapon damage around the fighter. A hit occurs at the same timestamp used by the visible animation. Recovery must finish before the next attack; a click within the last 250 ms can queue the next move. Blocking clears queued and current attacks without refunding already-spent attack stamina.
- **G drop / F pickup:** actual shared world weapons fall briefly and expire after 25 seconds. Picking up a borrowed weapon does not grant permanent ownership. Your purchased loadout returns after death. Being disarmed briefly staggers you before recovery.
- **Z / X / C:** aim at legs, body or head. Damage multipliers are 0.68 / 1.0 / 1.45. Actual impact height also depends on jumping and projectile travel. Helmets protect head hits; armour protects other regions. Move and weapon damage also matter. Each direct damage event is capped at 75, so a fresh fighter with at least 100 health cannot be killed by a single direct hit.
- **Bows, crossbows, slingshots:** server-simulated speed, gravity, travel time and swept collisions. Shields absorb some projectile damage. Facing an arrow with a timed blade parry or active weapon swing can reflect it toward its launch position. Ownership changes: subsequent damage and kill rewards belong to the defender. At most two reflections per projectile prevent endless ping-pong.
- **Stamina:** attacks, dodges, jumps, ropes and spells consume it. Blocking and absorbed guard hits consume none. Regeneration is 18/sec normally and 8/sec while guarding.
- **Balance and falling:** hits reduce balance by up to 45; leg hits reduce it faster. Balance regenerates at 12/sec. When it reaches zero, it resets to 35 and a random check may knock the fighter down for 1.25 seconds. Base chance is 75%, multiplied by 0.4 per footing upgrade, with a 3% floor. Fallen fighters cannot attack, block, walk or change weapons until recovering. Lasso has a separate 70% base trip chance, reduced by the same upgrades.
- **Ropes:** grappling rope pulls you toward a fighter or an aimed world landmark; lasso pulls the opponent toward you. Their reach is 14/9 metres, stamina cost 18, and attachment duration 1.6 seconds. They deal no direct damage, grant no XP by themselves and remain in their world.
- **Magic:** Stormblade drains additional enemy stamina and delays recovery; Frost Sabre/Frostbolt slow real movement; fire weapons/Firebolt apply short burning damage. Healing, a temporary ward and a short shockwave are purchasable spells. Casting has server-controlled stamina costs and cooldowns. Players must buy and equip spells before use.

## Store

There are **46 visible items** across melee, ranged, armour/shields/helmets, arcane weapons/spells, and upgrades. Added katana, falchion, estoc, warhammer, grappling rope and lasso. Prices and stats come from the server catalog. Arcane weapons cost 12,000–45,000 crowns and spells cost 8,000–32,000. Five persistent quick-slots hold purchased weapons; keys 1–5 switch them. Borrowed weapons cannot be assigned as owned equipment.

Each permanent upgrade adds **20 maximum health** and costs **12,000 × (existing upgrades + 1)²** crowns: 12,000, 48,000, then 108,000. It persists on respawn and adds only the new 20 health immediately to a living fighter. It is not a cheap full heal. Upgrades do not grant XP or skill. Crowns are game currency; purchases never use real money. Combat rewards cannot undo money spent in the store.

Permanent footing costs **16,000 × (existing footing upgrades + 1)²** crowns: 16,000, 64,000, then 144,000. Each purchase cuts the current knockdown probability by 60%, until the 3% minimum is reached. It persists on respawn and server restart.

## חשבון הניקוד בקצרה

הריגה נותנת נקודות מיומנות בגובה דרגת היריב, ועוד XP וכסף לפי הדרגה. מוות ליריב בדרגה נמוכה יותר מוריד יותר נקודות מיומנות. XP ודרגות לא נמחקים במוות; נקודות מיומנות נעצרות באפס. עצירה מתוזמנת לא צורכת סיבולת ונותנת XP ונקודות, וכך גם פריקת נשק והחזרת חץ. נשק שנאסף מהזירה נשאר זמני ואינו נחשב רכישה בחנות.
