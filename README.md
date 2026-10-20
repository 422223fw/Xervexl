# Xervexl — motlon

A playable Windows arena with **OpenGL and Vulkan in one native C++ executable**, an authoritative Python server, XP/ranks/skill, persistent accounts, a 47-item store and bots that fill empty slots. The same session survives changing graphics API in Settings. Eight initial procedural server instances offer desert, forest, snow, coast, volcanic, autumn, moonlit and marsh scenery; more instances open as they fill. The endless arena has no final round; eight additional round modes include 100-fighter squad survival.

## Play

Version 0.11 smooths footsteps, starts/stops, jumps and the following camera between server updates. The action bar shows WINDUP, CONTACT, RECOVERING, GUARD or READY, with the remaining time before the next attack. Motion prediction stops after 90 ms without fresh state; physical hit detection stays on the server.

Version 0.10 adds smoother attack arcs with matched contact velocity and acceleration, softer guard transitions, supported-foot walk cycles and a counter-swinging free hand. The server uses the same updated curves and limb positions for collision. Existing attack timing, damage and progression rules are preserved.

Each biome now has its own lighting, haze and sky colours, layered distant ridges, wind-blown tree crowns and cloth banners, worn circular paving, stone courses and nearby ground cover. Snow adds caps to vegetation and ruins; the coast has moving wave bands, and night arenas have moonlight and torch flames. These are procedural visuals in both renderers, with flat playable ground and the existing object collisions. Layered ground drawing prevents the former floor wedges from painting over surface details and characters; intersecting 3D objects still use the prototype's painter ordering.

Double-click **Play-Xervexl.cmd**. It starts a hidden local arena server and opens the game. No Windows administrator privileges are needed. Python 3.10+ is required; Python and the portable C++ compiler are already installed on this computer.

The compiled game is `build/Xervexl.exe`. Auto mode prefers Vulkan and falls back to OpenGL. **Both APIs are in the same file**, selectable in **Settings → Auto / OpenGL / Vulkan**; they do not render the same frame simultaneously. A compatible GPU driver is required. `powershell -NoProfile -ExecutionPolicy Bypass -File start.ps1 -Vulkan` remains supported.

**Sign up or sign in before playing.** The **Sign up to play** button opens registration; existing players can choose Sign in. Successful authentication continues into the selected arena. The server also rejects guest and unauthenticated arena requests. **New players start at rank 1, with 0 XP, 0 skill points, a knife and 100 crowns.** Existing accounts retain their earned rank and proportional progress through a backed-up, one-time XP conversion. After signing in, the home screen greets you and replaces Sign in with Logout. Eliminations earn XP, the victim's rank in skill, and rank-dependent crowns. Death removes skill, with a bigger penalty against a lower-rank killer. **SCORING.md** documents all formulas. New purchases equip automatically and fill an empty quick-slot.

| Control | Action |
|---|---|
| W / A / S / D | Move freely; in optional Directional mode walking also selects the cut |
| Mouse | Turn and look |
| Left mouse button | Easy mode: hold to attack in your walking direction: A left, D right, W overhead, S thrust; standing still alternates cuts |
| Middle mouse button | Direct thrust without needing to walk backward |
| V | Direct overhead cut |
| R / K | Deliberate clockwise / reverse spinning cut, 30 stamina |
| N / U / L | Rising cut / close pommel strike / non-damaging feint |
| Hold H | Revive a nearby downed squadmate for three uninterrupted seconds |
| 1 / 2 / 3 / 4 / 5 | Switch between owned quick-slot weapons |
| I | Inventory: choose one of five slots and assign a purchased weapon |
| Mouse wheel | Smooth zoom from bounded overhead view to first-person and back |
| Right mouse button | Hold to block; choose left/right/high/centre with A/D/W/S or mouse motion. Cancels your swing immediately; the blade animates into place |
| F3 | Show/hide authoritative head/body/limb hitboxes and weapon segments nearby |
| WASD / mouse while blocking | Both control modes: A left guard, D right guard, W high guard, S centre |
| Right mouse just before impact | Face and physically match the incoming attack within 180 ms for a perfect parry; XP + skill. A disarm also needs the much stricter grip/timing conditions |
| Z / X / C | Aim at legs / body / head |
| Q | Disarm an exhausted or recovering opponent |
| G / hold F | Drop weapon / recover a nearby weapon from the floor |
| B | Cast equipped purchased spell |
| T | Live skill / rank / XP / crowns / eliminations leaderboards |
| Shift | Short dodge, costs stamina |
| Space | Low jump, costs stamina |
| E | Armoury |
| Escape | Menu / resume; online combat keeps running |
| F12 | Save game-frame screenshot in `screenshots/capture.bmp` |

## Combat rules

- Holding a correctly directed blade guard costs no stamina. Physical blade contact and facing still determine whether a hit is stopped; a perfect parry retains its existing 180 ms timing window.
- Blocking immediately interrupts your swing and clears its buffered follow-up. It preserves the attack's remaining recovery and spent stamina, so tapping block cannot speed up a heavy weapon. The action bar shows when another attack is available.
- A dodge costs 24 stamina and lasts 320 ms. It interrupts the current swing and its buffer, keeps any longer existing recovery, and prevents starting another melee attack, shot or spell while evading. Projectiles already in flight continue normally.
- Entry/respawn protection lasts up to 1.5 seconds. Starting a legal weapon attack or casting a spell ends it immediately. Walking, guarding and rejected actions retain the remaining protection. The HUD states this rule while protection is active.
- Each swing can hit a particular target only once. Head, torso, arm and leg damage follows the actual animated hitboxes. Your owned health, grip and footing upgrades still apply.

Combat animations follow readable sword cuts, close guards and side steps observed in the supplied Saber Showdown trailer, using original human-shaped procedural geometry. Bent elbows and knees, fixed-length blades, limited arm reach, torso turns and a smooth return to guard replace the earlier rigid swings. Windup, impact and recovery use the authoritative server clock. A late attack click is buffered for up to 250 ms outside a dodge; blocking clears it and immediately cancels a swing. Overhead attacks cost more stamina and recover more slowly. Thrusts extend forward on a direct line and deal lower damage. A spinning cut turns once, deals reduced damage around you and costs 30 stamina. The first-person camera does not force a full rotation.

The improved cuts follow diagonal arcs with continuous wrist and blade velocity through the server's contact time, then settle back into guard. Overheads pass above the head in a vertical plane; thrusts extend and withdraw in a straight line. Disarming uses a distinct hook-and-pull motion. A spin first loads the weapon, turns once and recovers without jumping into its starting pose. Hips turn less than the torso during ordinary cuts, while the blade follows the fighter's aim. Both hands remain attached to the hilt of two-handed weapons within arm reach, including visible rear-hand support in first-person view. Client animation advances between state packets and stops extrapolating after 90 ms without a new server time. Standard cut contact now takes 240 ms and the whole cut 600 ms, with overheads at 340/760 ms and spins at 460/1,040 ms. Rising cuts, reverse spins, pommel strikes and non-damaging feints add distinct motions without changing the easy left/right mouse controls. Guard changes and attack-to-block transitions use the same 120 ms animation on the server and client. Pressing block cancels your swing immediately; stopping incoming damage requires your blade to reach and intersect it. These remain original procedural animations with compound body and weapon hitboxes, rather than motion capture or a recreation of undocumented Saber Showdown mechanics.

**Easy controls are the default.** Hold left click to attack according to your walking direction relative to your aim: **A = left cut, D = right cut, W = overhead, S = thrust**. Diagonals prefer their left/right component. Standing still alternates horizontal cuts. The next swing samples your current direction when it starts; turning or changing movement never converts a swing already in progress. Every move retains its recovery and stamina cost; release to stop automatic follow-ups. Right click cancels an attack and blocks. While holding right click, choose guard with A/D/W/S or move the mouse left/right/up/down. The server checks your selected direction and the animated blade position. You still need to look at the attacker and press block just before impact for a perfect parry. Changing direction while holding block does not reset the 180 ms perfect-parry window. Middle click thrusts, V cuts overhead, Q disarms and R spins; explicit move shortcuts take priority over walking direction. **Settings → Easy / Directional** switches controls and remembers the selection in private `data/controls.json`. Directional mode uses individual attack clicks; both modes use manual directional guards. Ranged weapons retain their normal held shot.

The carried sword also follows your movement with a small directional lean and step sway, visible in first person and third person. Starting, stopping and changing direction blend smoothly. Attack contact and directional guards retain their authored poses; both hands remain attached to a two-handed hilt.

Your body and footsteps follow walking direction; attack and guard turn the body toward your aim. Facing an attack with the matching guard absorbs it without stamina loss. Counter a left cut with right guard, a right cut with left guard, and an overhead with high guard. Centre guard covers thrusts; side cuts require the matching side and overheads require high guard. A correctly timed counter interrupts the attacker and earns parry XP/skill. Disarms are now rare: the opponent must be exhausted (under 25 stamina), within 1.8 metres and precisely aligned; Q has only an 8% base chance during exposed recovery, and an exceptionally timed 70 ms parry has a 4% base chance. Eligible attempts share a three-second retry delay per victim. Holding guard does not repeatedly earn XP.

Armour/helmets protect different hit regions, and heavy gear slows movement. Arrows have visible 3D shafts, heads and feathers. Face an arriving arrow and time a blade block to return it toward its launch position. Borrowed weapons do not add permanent ownership. Dodges briefly evade strikes. Death respawns you after 3.5 seconds. New spawns have 1.5 seconds of entry grace during which they neither deal nor receive damage.

**Recover your sword from the floor:** walk within 1.7 metres and hold **F**. A highlighted ground weapon, `[F] YOUR WEAPON` label and pickup prompt show the target. Your dropped weapon takes priority over nearby foreign weapons. Holding F retries while the sword lands or while you recover from being disarmed; one successful hold equips one weapon and needs a release before another pickup. G drops the current weapon voluntarily. Picking up while armed swaps weapons and drops the previous one; a punch/queued swing is cancelled during the 0.3-second equip recovery. Dead or fallen characters cannot pick up. Foreign weapons remain temporary and never add permanent inventory or currency.

**Armoury → Upgrades → Permanent grip** halves your remaining chance of losing a melee weapon with every purchase. It costs 4,000, then 16,000, then 36,000 crowns (4,000 × the next upgrade number squared). Grip applies immediately and persists through respawn, world changes and server restarts; it does not stop voluntary G drops or F pickup. The shop shows your current grip level and next price. Existing accounts receive level zero after a private backup without changing their earlier progress.

Repeated hits deplete balance and can knock you down. The expensive **Permanent footing** shop upgrade reduces that chance. Grappling rope pulls you toward a fighter or an aimed landmark; a lasso can trip and pull an opponent. Both are purchased weapons placed in your quick-slots.

Every elimination restores the living, upright killer to full maximum health, including shop health upgrades, and 100 stamina. Players and bots receive the same refill, including for ranged, magic and reflected-arrow eliminations.

**Automatic health recovery:** after four seconds without taking damage, you recover **2 HP per second**, up to your current maximum including purchased health upgrades. Moving or guarding does not stop recovery; another damaging hit restarts the four-second wait. The health bar turns green and reads **REGEN +2** while recovering. Burning and survival-circle damage interrupt recovery; dead, downed and eliminated fighters cannot heal themselves this way. Reviving a teammate starts a fresh recovery wait at half health. Recovery has the same rate for players and bots and does not grant extra XP or increase maximum health.

**Hitboxes and directional defence:** body collision uses separate head/torso boxes and animated arm/leg capsules. Melee must physically sweep the weapon through them. Hold right click and choose **A = left, D = right, W = high, S = centre**, or use mouse motion. Counter an incoming left cut with right guard, right cut with left guard, overhead with high guard and thrust with centre. A guard travels into place over 120 ms and its current blade position is used for collision. A held matching blade can stop a physically intercepted arrow; last-instant contact reflects it. A fully intercepted hit costs zero stamina; a wrong direction or uncovered body part can be struck. Shields reduce damage only where their visible volume intercepts it. Block/parry contact produces a spark at the actual collision point. Press **F3** to display the server's nearby body hitboxes and weapon segments; cyan marks a guarding blade. First person hides your own debug volumes; zoom out to inspect them.

## Multiplayer

**Each server instance allows at most 100 human combatants.** When the hundredth player enters and no spare instance of that biome has room, the backend immediately opens another isolated instance with a new procedural layout. The next player enters an available instance automatically; selecting a full server redirects to an available instance of its biome. Allocation is locked across concurrent requests. Respawning players still occupy their slot; bots and accounts browsing menus do not. Leaving or an inactive avatar frees a slot without logging the account out. Rejoining from the same account cannot consume a second slot. The paginated server selector refreshes occupancy every two seconds and shows the server number, human count, limit and bots. Your current server number and occupancy also appear in the combat HUD.

The server supplies enough bots to keep **at least ten total combatants in each active endless world**. When ten humans share a world, it removes that world's filler bots. Bot skill depths are shuffled among 2, 3, 4 and 5. They choose targets using distance, health and their own need for a finishing blow, react to visible attacks with depth-dependent delays, attack exposed guard directions, lead moving ranged targets, dodge incoming projectiles and steer around landmarks. Two native clients can fight in the same authoritative arena, including clients using different graphics APIs. The Worlds screen lets you pick a server or enter another random world. Automatic entry prefers a populated instance with space. Each biome generates a different layout of rocks, columns, ruins or trees, with gaps for movement. Landmarks are shared from server seeds; damage, arrows, dropped weapons and ropes remain inside their instance. Equipment and progress follow you between instances, which share accounts and leaderboards.

These instances run **inside one authoritative Python backend process**, at the same server address. Opening an instance does not provision another physical computer, cloud host or operating-system process. Instance numbers/layouts last for that backend run; accounts, remembered sign-in and bot learning persist across restarts. Hosting still requires the reachable machine described below.

For another machine on your own network, run:

```powershell
python server.py --host 0.0.0.0 --port 8765
```

On each client, open Settings and enter `http://SERVER-LAN-IP:8765`. The host must be reachable; the project does not open router ports or change Windows firewall settings.

For internet play, deploy `server.py` on a host and terminate HTTPS with a reverse proxy. Point clients at its HTTPS URL. As requested, no public server has been deployed yet. There is no fake matchmaking or invented online player count.

## Round modes and world workshop

Open **GAME MODES** from Home or **MODES** in the Armoury. The eight free official modes are Last Squad/100, Last Fighter/100, Last Duo/100, Squad Skirmish/40, Clash/10v10, Duel/first to 3, Blade Brawl and Archer Squads. Bots fill each lobby to its stated population; a running survival match admits newcomers into another lobby. Ordinary endless instances retain their independent 100-human limit.

**Last Squad / 100** contains 25 squads of four. Teammates cannot damage, parry-farm or rope each other. Lethal damage downs a fighter for up to 24 seconds when an upright squadmate remains; finishing damage, bleeding out or a squad wipe eliminates them for that round. Walk within 2.2 metres and hold **H** without moving, attacking, blocking or taking damage for three seconds to revive at half health. Multiple rescuers do not accelerate it. Bots also approach and rescue endangered nearby teammates when the tactical situation permits. A shrinking marked safe circle discourages indefinite hiding. The last upright squad wins **650 XP, 350 crowns and 25 skill per registered squad member**, including eliminated/disconnected members on that round's roster. Rewards apply once; a member moving to another arena retains them. The round restarts after the result screen. Duels and Clash use respawns and an elimination target instead.

**WORLD WORKSHOP** provides a top-down map editor for rocks, trees, ruins and pillars, with size/height controls, eight biomes, player/team sizes and survival/respawn rules. Left click places objects; right click erases. Type event code in the adjacent editor; Enter starts a line and Ctrl+A/Ctrl+V replaces/pastes code. Save the world, then choose **PLAY SAVED WORLD**. Saved maps also appear in the mode catalog and can be reopened in the editor. See [WORKSHOP.md](WORKSHOP.md) for the actual programming grammar and examples.

Workshop code is a small validated event language, with 48 instructions, conditions and actions rather than arbitrary Python/Lua execution. It can change match weapons, health, stamina, score and local XP/crowns. Custom modes are unranked: their scripted rewards and combat stats stay inside the match and do not inflate persistent accounts or global leaderboards. Official modes supply persistent victory rewards. Creator ownership, map bounds and object spacing are checked by the authoritative server; up to 24 maps per creator and 80 objects per map are saved in private `data/accounts.workshop.json`. No publishing/hosting service is required for local creation.

The two original looping instrumental scores use separate menu/combat arrangements. Music continues underneath combat sounds. **Settings / MUSIC** controls mute and volume and saves them in private `data/audio.json`.

## Accounts and JSON

Bots also **learn from their actual battles**, including fights against each other when no humans are present. Shared, small action-value tables for each depth and weapon/range/guard/health/stamina situation correct the existing 2–5-step tactical forecast. Damage dealt, real blocks, parries, disarms and eliminations reward decisions; misses, damage received, lost weapons and deaths penalize them. Ranged outcomes remain attached to the original shot even after the shooter changes actions. Idle blocking earns no positive feedback. Occasional exploration chooses among close tactical alternatives. Recent results continue updating old habits, so bots can adapt when opponents change their tactics.

The memory is saved every five seconds of server time and on clean shutdown in private **`data/bot_learning.json`**, and loaded on restart. Bots of the same depth/context share experience, including replacement bots and bots in other worlds. The file contains aggregate combat statistics without player names, account IDs or credentials. Storage is limited to 4,096 contexts; old contexts are replaced as new situations occur. Atomic checkpoints retry transient Windows locks; invalid memory is privately backed up before recovery. Test servers keep separate memories beside their own account files. This is online contextual action-value learning, not neural-network training or a guarantee that every successive battle is better. Reflex delays, planning depth, weapon damage and bot health do not increase through learning.

The server automatically creates **`data/accounts.json`** when missing. It stores usernames, emails, salted PBKDF2-SHA256 password hashes, equipment and progress; passwords are never stored in plain text. Runtime data is excluded from Git, together with logs and local settings. `accounts.example.json` is an empty public template; `project.json` contains public project metadata.

**Sign in once and stay signed in until Logout.** Sign up also remembers the new account. Closing/reopening the native game or restarting the server restores the account without asking for the password again. The client stores its bearer token and selected server in private **`data/login-session.bin`**, encrypted with Windows DPAPI for the current Windows user. It does not save the password. The server keeps only hashed bearer grants in private **`data/sessions.json`**, with a credential fingerprint to invalidate old grants after a password reset. Remembered authentication has no inactivity timeout; an idle arena avatar is still removed after 60 seconds to free a combatant slot, and the account remains signed in.

Logout clears the local remembered account immediately and revokes its server grant. If the server is unavailable, the client remains logged out and keeps an encrypted pending revocation to retry when that server is reachable again. A late account-restore response cannot undo Logout. Temporary connection failures preserve the remembered account and retry; the home screen shows restoration status with an available Logout button. Tokens are kept separate for each server address. Password recovery invalidates remembered sign-ins as well as active sessions. Copying the portable game to another Windows user/computer requires a fresh sign-in. After installing this update, sign in once to establish the new remembered session.

**Do not push real email addresses, password hashes, session grants, reset codes or SMTP credentials to GitHub.** JSON files in a source repository cannot provide secure public authentication or email delivery. Back up the private `data/` directory before moving the server; do not replace trained or other projects' data. This game does not modify Active-Connection files.

Password recovery has working request/reset endpoints and a client screen. Configure these environment variables on the server to deliver one-use reset codes by SMTP with STARTTLS:

```powershell
$env:SMTP_HOST = "smtp.your-provider.example"
$env:SMTP_PORT = "587"
$env:SMTP_USER = "your-smtp-user"
$env:SMTP_PASSWORD = "your-smtp-secret"
$env:SMTP_FROM = "games@your-domain.example"
python server.py
```

Recovery requires both the matching username and email. Codes expire in 15 minutes, can be used once, and invalidate existing sessions when used. With no SMTP service configured, the UI clearly reports that email recovery is unavailable. Actual email delivery has not been tested because no email service was supplied.

## Build and verify

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1
python -m unittest discover -s tests -v
python tests/simulate_bots.py
```

`build.ps1 -Compiler C:\path\to\g++.exe` supports another MinGW-w64 compiler. The checked-in headers, native collision-pose exporter and fixed SPIR-V assembler make the build reproducible without a Vulkan SDK, npm, or administrator installation. `tools/make_shaders.py` assembles only the two fixed shaders represented by `shaders/arena.vert` and `arena.frag`; if their logic changes, update the assembler or use a standard GLSL compiler.

Smoke tests: `build/Xervexl.exe --smoke --opengl`, `--smoke --vulkan`, `--smoke --arena`, and `--smoke --arena --switch`. Arena entry opens Sign up until authenticated. `--server=http://127.0.0.1:18765` allows an isolated preview server. Reports and **GPU-frame** screenshots are saved before exit. `--shop --ranged`, `--shop --arcane`, `--shop --health`, `--leaders`, `--inventory` and `--worlds` inspect these screens. Arena options `--first-person`, `--overhead` and `--world=0` through `--world=4` inspect camera modes and biomes. `--preview-move=left --preview-phase=0.18` displays an isolated visual mannequin without an arena session; other moves and `guard_up/left/right/centre` can be inspected the same way. Tests cover mandatory registration, backed-up XP migration, very high ranks, tactical bots, exact starting values, animation timing/buffering, scoring, inventory, directional guard/cancellation, footing, ropes, room isolation, store balances, health upgrades, projectile ownership, body regions, spells, respawn and multiplayer. `tests/pose_checks.cpp` checks blade length, bone length, attached two-hand grips, reach and smooth recovery across 32,922 animation samples, including head/body/leg aim, plus continuous contact velocity, guard-cancellation transitions and bounded animation-clock extrapolation.

## Prototype limits

This is a playable prototype, not a finished commercial game or a photorealistic production. Added features and smoke tests do not establish a commercial value of 100 NIS or replace human playtesting. Each world has a finite physical boundary and continuous play; it does **not** support literally infinite simultaneous people. The authoritative 100-human limit and automatic expansion are tested with synthetic occupants and concurrent HTTP joins, not a performance benchmark with 100 native clients. The backend begins with eight arena instances and creates more on demand, sharing one process and its available CPU/RAM. Fighter separation runs per instance but remains quadratic within each instance; other combat searches and HTTP polling also limit scalability. There is no public hosting, external matchmaking directory, moderation, account email verification, cloud deployment automation or production anti-cheat service.

Bot search runs 2–5 steps with a ten-state beam, forecasting damage, guard direction, range, cooldowns, stamina, crowds and the health refill from a finishing blow. This remains a simplified opponent-reply model, not exhaustive minimax, optimal play or general human reasoning. Tactical reactions observe shown attack animations rather than unrevealed input. Rank and AI depth are distinct. Melee sweeps animated weapon segments against oriented head/torso boxes and articulated arm/leg capsules; projectiles use swept segments against the same shapes. These analytic hitboxes approximate the character surface, including jumping and falling. Native animation curves are exported to assets/combat_geometry.json for the authoritative server; build.ps1 regenerates that public asset atomically. The server uses bounded substeps during the active swing and per-tick victim poses; rendering interpolation and network latency still affect visual agreement. Jumping changes impact height and is not an invulnerability power. Falling uses an animated pose, not a physics ragdoll. Rope pulling uses simple temporary constraints, not a full rope/climbing simulation. The camera can pass through scenery. The supplied video is a short trailer, so this update follows its visible fighting style rather than reproducing undocumented Saber Showdown internals. Economy and difficulty have not undergone a human playtest; rankings are per server.

3D geometry is projected on the CPU and triangles are sorted before drawing. OpenGL uses a fixed-function triangle stream; Vulkan uses a real instance/device, swapchain, command buffers, vertex buffer, SPIR-V graphics pipeline and GPU presentation. There is no GPU depth buffer, advanced lighting, textures, animation skeleton, positional audio or modern postprocessing yet. Music uses an independent stereo Windows audio stream with saved volume/mute settings; combat effects play over it. The initial graphics are procedural and stylized.

The local server is a threaded Python HTTP prototype with atomic private JSON storage and rate limiting on account requests. Internet production requires hosting, HTTPS, hardened operations and load testing. Reset mail delivery requires your SMTP service. Source files alone in GitHub are not a running online game.

## Third-party components

See `THIRD_PARTY.md`. Art, short combat sounds and both original instrumental scores are generated by the project. No Saber Showdown assets or code are included.

## הוראות קצרות

ב־**GAME MODES** אפשר לבחור **Last Squad / 100**: 25 קבוצות של ארבעה, עם בוטים כשחסרים שחקנים. מחזיקים **H** ליד חבר שנפל כדי להחיות אותו במשך שלוש שניות. הקבוצה האחרונה שורדת וזוכה לכל שחקן רשום ב־650 XP, ב־350 מטבעות וב־25 נקודות מיומנות. **WORLD WORKSHOP** פותח עורך עולם וקוד חוקים; **SAVE WORLD** שומר ו־**PLAY SAVED WORLD** מריץ. תגמולי מודים אישיים נשארים בתוך הקרב; מצבים רשמיים מעניקים התקדמות קבועה. אפשר להשתיק מוזיקה ולשנות עוצמה בהגדרות. N מוסיף חיתוך עולה, K סיבוב הפוך, U מכה קרובה בידית ו־L הטעיה.

לחצי פעמיים על **Play-Xervexl.cmd**, ואז **Sign up to play**. חייבים להירשם או להתחבר כדי לשחק. חשבון חדש מתחיל בדרגה 1, עם 0 נקודות מיומנות ו־100 מטבעות. אחרי Sign in ההתחברות נשמרת גם בסגירה ופתיחה של המשחק ובהפעלה מחדש של השרת, עד שלוחצים על Logout. הסיסמה אינה נשמרת במחשב; נשמר אסימון מוצפן. גם אם השרת אינו זמין בזמן Logout, המשחק נשאר מנותק מהחשבון ומנסה להשלים את הניתוק מול השרת בהמשך.

כל מופע שרת מוגבל ל־100 שחקנים אנושיים. כשמופע מתמלא נפתח מופע נוסף לפי הצורך, והמצטרפים הבאים נכנסים למקום פנוי. **Explore Worlds** מציג את רשימת השרתים, התפוסה והבוטים, עם מעבר בין עמודים. המופעים פועלים כרגע בתוך אותו שרת מקומי; לא מוקמים אוטומטית מחשבים או שרתי ענן.

מצב Easy מופעל כברירת מחדל: WASD לתנועה, העכבר למבט ומחזיקים קליק שמאלי למכה לפי כיוון ההליכה: A חיתוך שמאלה, D חיתוך ימינה, W מכה מלמעלה ו־S דקירה. בעמידה החיתוכים מתחלפים. גם נשיאת החרב נוטה לכיוון ההליכה ומתנודדת בעדינות עם הצעדים, בגוף ראשון ושלישי. קליק ימני מבטל התקפה וחוסם. צריך להסתכל לכיוון היריב וללחוץ בזמן כדי לבצע חסימה מושלמת. הפלת חרב נדירה מאוד ודורשת יריב מותש, טווח קצר ודיוק; בחנות Armoury → Upgrades אפשר לשפר Grip, וכל שדרוג מקטין בחצי את הסיכון לאבד את החרב. כיוון החסימה נבחר בעזרת העכבר או A/D/W/S; החזקת חסימה אינה נותנת שוב ושוב חסימה מושלמת. לחיצה על הגלגלת דוקרת, V מכה מלמעלה, Q פירוק נשק ו־R סיבוב. אפשר לבחור חסימה ידנית ומכות בלחיצות נפרדות דרך **Settings → Directional**. 1–5 מחליפים נשקים, I פותח Inventory, E חנות וגלגלת העכבר משנה זום עד גוף ראשון.

הבוטים לומדים מתוצאות הקרבות שלהם נגד בוטים ושחקנים. הזיכרון נשמר בקובץ פרטי **data/bot_learning.json** ונטען מחדש בהפעלה הבאה. הם מתאימים בחירות לפי הצלחות וכישלונות; אין הבטחה שכל קרב יהיה טוב מקודמו. דרגה 2 עולה 79 XP, דרגה 3 עוד 237, דרגה 4 עוד 948, וכך הלאה בהכפלה בדרגה הבאה. הכוחות והנשקים הקסומים נשארו. המשחק עובד מקומית עם בוטים; שרת ציבורי ושירות מייל עדיין אינם מוגדרים.

??**GAME MODES** ???? ????? **Last Squad / 100**: 25 ?????? ?? ?????, ?? ????? ??????? ??????. ??????? **H** ??? ??? ???? ??? ?????? ???? ???? ???? ?????. ?????? ??????? ????? ????? ??? ???? ???? ??650 XP, ??350 ?????? ???25 ?????? ???????. **WORLD WORKSHOP** ???? ???? ???? ???? ?????, ??**SAVE WORLD / PLAY SAVED WORLD** ???? ????? ????. ?????? ????? ?????? ?????? ???? ????; ????? ?????? ??????? ??????? ?????. ??????? ????? ?????? ??????? ????? ???????. N ????? ????? ????, K ????? ????, U ??? ????? ????? ??L ?????.
