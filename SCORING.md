# Xervexl 0.9.0 — progression and combat rules

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

Living fighters also recover **2 HP/second after four seconds without damage**, capped at their existing maximum health. The server counts only the part of a tick after that delay; another damaging hit restarts it. Blocking an entire hit does not interrupt recovery. Burning prevents recovery, and survival-circle damage resets the wait. Dead, downed or eliminated fighters and inactive round lobbies cannot regenerate. A squad revive restores half health and begins a fresh four-second wait. Players and bots share this rule. Passive healing grants no XP, skill, crowns or permanent maximum-health increase, and clients cannot submit healing rates or health values.

Leaderboards cover skill, rank, XP, current crowns and eliminations. They include registered accounts on this server and active combatants, with BOT/PLAYER labels. They do not aggregate independent internet servers. Playing requires a registered account; the old guest endpoint is disabled.

## Combat

- **Physical hitboxes:** head and torso use oriented boxes; arms/legs use capsules around their animated bones. Jumping, falling and guard poses move them. The server sweeps the native blade animation at bounded substeps and resolves each victim once per swing. Projectiles use the same body shapes and select the first intersected target. A guard needs both the correct direction and blade contact before the body; shields protect only their own volume. Mouse motion or A/D/W/S selects left/right/high/centre while blocking in both control modes. Guard movement takes 120 ms and changing direction does not restart the perfect-parry clock. F3 displays authoritative nearby collision volumes.

- **Movement-directed sword:** holding the primary attack in Easy mode chooses left/right cuts when moving left/right, overhead when advancing and thrust when retreating, relative to aim. Diagonals prefer left/right; standing still alternates cuts. The authoritative server samples direction when the next attack starts and uses that move's existing cost, windup and recovery. Movement does not change a swing already in flight. Releasing the primary attack clears automatic follow-ups; block still cancels immediately. Dedicated move keys retain their own move, and ranged weapons keep their normal shot. The carried weapon leans/sways with walking, with attached grips and unchanged contact/guard poses.
- **Perfect parry:** face the attack tightly, select its matching direction and physically intercept the blade within 180 ms of starting guard. It costs zero stamina, interrupts the attacker and awards the parry reward. It no longer automatically drops their weapon. A rare counter-disarm additionally requires the attacker to have under 25 stamina, contact within 1.8 metres, aim within 0.25 radians and guard started within 70 ms of impact; its base chance is only 4%. Match left cuts with right guard, right cuts with left guard, overheads with high guard, and thrusts with centre guard. Centre guard covers thrusts; it does not also block horizontal cuts. Empty hands cannot parry. Holding an aligned guard absorbs melee damage with no stamina loss but no repeated XP reward. A mismatched blade guard provides no automatic damage reduction; a physical shield can still protect its own area. Blocking cancels your ongoing attack immediately.
- **Q disarm:** a deliberate 300 ms windup costing 22 stamina. Both fighters need a melee weapon; the victim must have under 25 stamina, be recovering with no active windup and have their guard down. The animated blades must touch, within 1.8 metres and 0.25 radians of aim. Even then, base success is only 8%, reduced further by the victim's permanent grip. Every eligible attempt locks further disarm attempts against that victim for three seconds, shared by all opponents. Healthy, protected, fallen, downed or unarmed fighters cannot be disarmed. Failure awards no disarm XP/skill and causes no skill penalty; a successful parry still earns its separate reward. Empty hands cannot be disarmed repeatedly.
- **Cuts/thrust/spin:** left/right cuts cost 12 stamina and use a 240 ms windup, overhead costs 20 with 340 ms, direct thrust costs 12 with 240 ms. The optional R spinning cut costs 30, winds up for 460 ms and deals 82% weapon damage around the fighter. The blade is swept through the active contact interval of the visible animation and must intersect an actual body hitbox; a target takes damage once per swing. Recovery must finish before the next attack; a click within the last 250 ms can queue the next move. Blocking clears queued and current attacks without refunding already-spent attack stamina.
- **G drop / F pickup:** actual shared world weapons fall briefly and expire after 25 seconds. Picking up a borrowed weapon does not grant permanent ownership. Your purchased loadout returns after death. Being disarmed briefly staggers you before recovery.
- **Z / X / C:** aim at legs, body or head. Damage multipliers are 0.68 / 1.0 / 1.45. The actual intersected head, torso or limb determines the hit region. Aiming at a region does not declare a hit there. Jumping, walking poses, falling and projectile travel move the geometry. Helmets protect head hits; armour protects other regions. Move and weapon damage also matter. Each direct damage event is capped at 75, so a fresh fighter with at least 100 health cannot be killed by a single direct hit.
- **Bows, crossbows, slingshots:** server-simulated speed, gravity, travel time and swept collisions. Shields absorb some projectile damage. A timed matching guard or an active swing can reflect an arrow only when its swept path intersects the actual blade, returning it toward its launch position. Ownership changes: subsequent damage and kill rewards belong to the defender. At most two reflections per projectile prevent endless ping-pong.
- **Stamina:** attacks, dodges, jumps, ropes and spells consume it. Blocking and absorbed guard hits consume none. Regeneration is 18/sec normally and 8/sec while guarding.
- **Balance and falling:** hits reduce balance by up to 45; leg hits reduce it faster. Balance regenerates at 12/sec. When it reaches zero, it resets to 35 and a random check may knock the fighter down for 1.25 seconds. Base chance is 75%, multiplied by 0.4 per footing upgrade, with a 3% floor. Fallen fighters cannot attack, block, walk or change weapons until recovering. Lasso has a separate 70% base trip chance, reduced by the same upgrades.
- **Ropes:** grappling rope pulls you toward a fighter or an aimed world landmark; lasso pulls the opponent toward you. Their reach is 14/9 metres, stamina cost 18, and attachment duration 1.6 seconds. They deal no direct damage, grant no XP by themselves and remain in their world.
- **Magic:** Stormblade drains additional enemy stamina and delays recovery; Frost Sabre/Frostbolt slow real movement; fire weapons/Firebolt apply short burning damage. Healing, a temporary ward and a short shockwave are purchasable spells. Casting has server-controlled stamina costs and cooldowns. Players must buy and equip spells before use.

## Store

There are **47 visible items** across melee, ranged, armour/shields/helmets, arcane weapons/spells, and upgrades. Added katana, falchion, estoc, warhammer, grappling rope, lasso and permanent grip. Prices and stats come from the server catalog. Arcane weapons cost 12,000–45,000 crowns and spells cost 8,000–32,000. Five persistent quick-slots hold purchased weapons; keys 1–5 switch them. Borrowed weapons cannot be assigned as owned equipment.

Each permanent upgrade adds **20 maximum health** and costs **12,000 × (existing upgrades + 1)²** crowns: 12,000, 48,000, then 108,000. It persists on respawn and adds only the new 20 health immediately to a living fighter. It is not a cheap full heal. Upgrades do not grant XP or skill. Crowns are game currency; purchases never use real money. Combat rewards cannot undo money spent in the store.

Permanent footing costs **16,000 × (existing footing upgrades + 1)²** crowns: 16,000, 64,000, then 144,000. Each purchase cuts the current knockdown probability by 60%, until the 3% minimum is reached. It persists on respawn and server restart.

**Permanent grip**, under **Armoury → Upgrades**, costs **4,000 × (existing grip upgrades + 1)²** crowns: 4,000, 16,000, then 36,000. Every purchase halves the remaining disarm chance: Q attempts become 8%, 4%, 2%, 1%, and precisely timed counter-disarms become 4%, 2%, 1%, 0.5%. These percentages apply only after all contact/exhaustion/recovery conditions pass. The upgrade takes effect immediately and follows the account through death, world changes and remembered sign-in/server restart. It does not prevent G voluntary drops or change F recovery. Bots use the same rules, with starting grip 0/0/1/2 at thinking depths 2/3/4/5. Existing accounts receive grip level zero after a private byte-for-byte backup, preserving all earlier values.

## חשבון הניקוד בקצרה

הריגה נותנת נקודות מיומנות בגובה דרגת היריב, ועוד XP וכסף לפי הדרגה. מוות ליריב בדרגה נמוכה יותר מוריד יותר נקודות מיומנות. XP ודרגות לא נמחקים במוות; נקודות מיומנות נעצרות באפס. עצירה מתוזמנת לא צורכת סיבולת ונותנת XP ונקודות, וכך גם פריקת נשק והחזרת חץ. נשק שנאסף מהזירה נשאר זמני ואינו נחשב רכישה בחנות.
