# Xervexl — motlon

A playable Windows arena with **OpenGL and Vulkan in one native C++ executable**, an authoritative Python server, XP/ranks/skill, persistent accounts, a 46-item store and bots that fill empty slots. The same session survives changing graphics API in Settings. Five shared procedural worlds offer desert, forest, snow, coast and volcanic scenery. There is no match winner or final round.

## Play

Double-click **Play-Xervexl.cmd**. It starts a hidden local arena server and opens the game. No Windows administrator privileges are needed. Python 3.10+ is required; Python and the portable C++ compiler are already installed on this computer.

The compiled game is `build/Xervexl.exe`. Auto mode prefers Vulkan and falls back to OpenGL. **Both APIs are in the same file**, selectable in **Settings → Auto / OpenGL / Vulkan**; they do not render the same frame simultaneously. A compatible GPU driver is required. `powershell -NoProfile -ExecutionPolicy Bypass -File start.ps1 -Vulkan` remains supported.

**Sign up or sign in before playing.** The **Sign up to play** button opens registration; existing players can choose Sign in. Successful authentication continues into the selected arena. The server also rejects guest and unauthenticated arena requests. **New players start at rank 1, with 0 XP, 0 skill points, a knife and 100 crowns.** Existing accounts retain their earned rank and proportional progress through a backed-up, one-time XP conversion. After signing in, the home screen greets you and replaces Sign in with Logout. Eliminations earn XP, the victim's rank in skill, and rank-dependent crowns. Death removes skill, with a bigger penalty against a lower-rank killer. **SCORING.md** documents all formulas. New purchases equip automatically and fill an empty quick-slot.

| Control | Action |
|---|---|
| W / A / S / D | Move; walking direction also selects the sword move |
| Mouse | Turn and look |
| Left mouse button | Attack: A left cut, D right cut, W overhead, S thrust; standing clicks alternate left/right cuts |
| Middle mouse button | Direct thrust without needing to walk backward |
| R | Deliberate spinning cut; longer commitment and 30 stamina |
| 1 / 2 / 3 / 4 / 5 | Switch between owned quick-slot weapons |
| I | Inventory: choose one of five slots and assign a purchased weapon |
| Mouse wheel | Smooth zoom from bounded overhead view to first-person and back |
| Right mouse button | Block; cancels your attack immediately, uses no stamina |
| WASD / mouse while blocking | A left guard, D right guard, W high guard, S centre; mouse direction also selects |
| Right mouse just before impact | Face and match the incoming attack within 180 ms to disarm; XP + skill |
| Z / X / C | Aim at legs / body / head |
| Q | Disarm an exhausted or recovering opponent |
| G / F | Drop weapon / pick up nearby weapon |
| B | Cast equipped purchased spell |
| T | Live skill / rank / XP / crowns / eliminations leaderboards |
| Shift | Short dodge, costs stamina |
| Space | Low jump, costs stamina |
| E | Armoury |
| Escape | Menu / resume; online combat keeps running |
| F12 | Save game-frame screenshot in `screenshots/capture.bmp` |

Combat animations follow readable sword cuts, close guards and side steps observed in the supplied Saber Showdown trailer, using original human-shaped procedural geometry. Bent elbows and knees, fixed-length blades, limited arm reach, torso turns and a smooth return to guard replace the earlier rigid swings. Windup, impact and recovery use the authoritative server clock. A late attack click is buffered for up to 250 ms; blocking clears it and immediately cancels a swing. Overhead attacks cost more stamina and recover more slowly. Thrusts have extra reach and a narrow cone but lower damage. A spinning cut turns once, deals reduced damage around you and costs 30 stamina. The first-person camera does not force a full rotation.

Your body and footsteps follow walking direction; attack and guard turn the body toward your aim. Facing an attack with the matching guard absorbs it without stamina loss. Counter a left cut with right guard, a right cut with left guard, and an overhead with high guard. A centred cross guard also covers horizontal cuts and thrusts. A correctly timed counter disarms even a full-stamina attacker. Holding guard does not repeatedly earn XP.

Armour/helmets protect different hit regions, and heavy gear slows movement. Arrows have visible 3D shafts, heads and feathers. Face an arriving arrow and time a blade block to return it toward its launch position. Borrowed weapons do not add permanent ownership. Dodges briefly evade strikes. Death respawns you after 3.5 seconds. New spawns have 1.5 seconds of entry grace during which they neither deal nor receive damage.

Repeated hits deplete balance and can knock you down. The expensive **Permanent footing** shop upgrade reduces that chance. Grappling rope pulls you toward a fighter or an aimed landmark; a lasso can trip and pull an opponent. Both are purchased weapons placed in your quick-slots.

Every elimination restores the living killer to full maximum health, including shop health upgrades, and 100 stamina. Players and bots receive the same refill, including for ranged, magic and reflected-arrow eliminations.

## Multiplayer

The server supplies enough bots to keep **at least ten total combatants in each active world**. When ten humans share a world, it removes that world's filler bots. Bot skill depths are shuffled among 2, 3, 4 and 5. They choose targets using distance, health and their own need for a finishing blow, react to visible attacks with depth-dependent delays, attack exposed guard directions, lead moving ranged targets, dodge incoming projectiles and steer around landmarks. Two native clients can fight in the same authoritative arena, including clients using different graphics APIs. The Worlds screen lets you pick a biome or enter another random world. Automatic entry prefers a populated human world. Each biome now generates a different layout of rocks, columns, ruins or trees, with gaps for movement. Landmarks are shared from server seeds; damage, arrows, dropped weapons and ropes remain inside their world. Equipment and progress follow you between worlds.

For another machine on your own network, run:

```powershell
python server.py --host 0.0.0.0 --port 8765
```

On each client, open Settings and enter `http://SERVER-LAN-IP:8765`. The host must be reachable; the project does not open router ports or change Windows firewall settings.

For internet play, deploy `server.py` on a host and terminate HTTPS with a reverse proxy. Point clients at its HTTPS URL. As requested, no public server has been deployed yet. There is no fake matchmaking or invented online player count.

## Accounts and JSON

The server automatically creates **`data/accounts.json`** when missing. It stores usernames, emails, salted PBKDF2-SHA256 password hashes, equipment and progress; passwords are never stored in plain text. Session tokens remain in server/client memory. Runtime data is excluded from Git, together with logs and local settings. `accounts.example.json` is an empty public template; `project.json` contains public project metadata.

**Do not push real email addresses, password hashes, reset codes or SMTP credentials to GitHub.** JSON files in a source repository cannot provide secure public authentication or email delivery. Back up `data/accounts.json` before moving the server; do not replace trained or other projects' data. This game does not modify Active-Connection files.

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

`build.ps1 -Compiler C:\path\to\g++.exe` supports another MinGW-w64 compiler. The checked-in headers and fixed SPIR-V assembler make the build reproducible without a Vulkan SDK, npm, or administrator installation. `tools/make_shaders.py` assembles only the two fixed shaders represented by `shaders/arena.vert` and `arena.frag`; if their logic changes, update the assembler or use a standard GLSL compiler.

Smoke tests: `build/Xervexl.exe --smoke --opengl`, `--smoke --vulkan`, `--smoke --arena`, and `--smoke --arena --switch`. Arena entry opens Sign up until authenticated. `--server=http://127.0.0.1:18765` allows an isolated preview server. Reports and **GPU-frame** screenshots are saved before exit. `--shop --ranged`, `--shop --arcane`, `--shop --health`, `--leaders`, `--inventory` and `--worlds` inspect these screens. Arena options `--first-person`, `--overhead` and `--world=0` through `--world=4` inspect camera modes and biomes. `--preview-move=left --preview-phase=0.18` displays an isolated visual mannequin without an arena session; other moves and `guard_up/left/right/centre` can be inspected the same way. Tests cover mandatory registration, backed-up XP migration, very high ranks, tactical bots, exact starting values, animation timing/buffering, scoring, inventory, directional guard/cancellation, footing, ropes, room isolation, store balances, health upgrades, projectile ownership, body regions, spells, respawn and multiplayer. `tests/pose_checks.cpp` checks blade length, bone length, reach and smooth recovery across 18,022 animation samples, including head/body/leg aim.

## Prototype limits

This is a playable prototype, not a finished commercial game or a photorealistic production. Each world has a finite physical boundary and continuous play; it does **not** support literally infinite simultaneous people. There is no measured large-scale player capacity. Each server has five shared arena rooms, and collision checks scale quadratically with population. There is no public hosting, matchmaking directory, moderation, account email verification, server deployment automation or production anti-cheat service.

Bot search runs 2–5 steps with a ten-state beam, forecasting damage, guard direction, range, cooldowns, stamina, crowds and the health refill from a finishing blow. This remains a simplified opponent-reply model, not exhaustive minimax, optimal play or general human reasoning. Tactical reactions observe shown attack animations rather than unrevealed input. Rank and AI depth are distinct. Melee uses distance/angle/height hit regions; projectiles use swept segments against fighter capsules. These approximate collisions rather than per-bone meshes. Jumping changes impact height and is not an invulnerability power. Falling uses an animated pose, not a physics ragdoll. Rope pulling uses simple temporary constraints, not a full rope/climbing simulation. The camera can pass through scenery. The supplied video is a short trailer, so this update follows its visible fighting style rather than reproducing undocumented Saber Showdown internals. Economy and difficulty have not undergone a human playtest; rankings are per server.

3D geometry is projected on the CPU and triangles are sorted before drawing. OpenGL uses a fixed-function triangle stream; Vulkan uses a real instance/device, swapchain, command buffers, vertex buffer, SPIR-V graphics pipeline and GPU presentation. There is no GPU depth buffer, advanced lighting, textures, animation skeleton, positional audio or modern postprocessing yet. The initial graphics are procedural and stylized.

The local server is a threaded Python HTTP prototype with atomic private JSON storage and rate limiting on account requests. Internet production requires hosting, HTTPS, hardened operations and load testing. Reset mail delivery requires your SMTP service. Source files alone in GitHub are not a running online game.

## Third-party components

See `THIRD_PARTY.md`. Art and short combat sounds are generated by the project. No Saber Showdown assets or code are included.

## הוראות קצרות

לחצי פעמיים על **Play-Xervexl.cmd**, ואז **Sign up to play**. חייבים להירשם או להתחבר כדי לשחק. חשבון חדש מתחיל בדרגה 1, עם 0 נקודות מיומנות ו־100 מטבעות. לתנועה: WASD ועכבר; כיוון התנועה בוחר את מהלך התקיפה בלחיצה שמאלית. בעמידה החתכים מתחלפים בין שמאל וימין. לחיצה על גלגלת העכבר דוקרת, R מבצע חתך בסיבוב. לחיצה ימנית מבטלת התקפה וחוסמת בלי צריכת סיבולת. חסימה מתוזמנת בכיוון הנכון מפילה את חרב היריב או מחזירה חץ. 1–5 מחליפים נשקים, I פותח Inventory, וגלגלת העכבר עוברת ממבט מלמעלה לגוף ראשון. E פותח את החנות; Worlds בוחר עולם. דרגה 2 עולה 79 XP, דרגה 3 עוד 237, דרגה 4 עוד 948, וכך הלאה בהכפלה בדרגה הבאה. הכוחות והנשקים הקסומים נשארו לבחירתך. המשחק עובד מקומית עם בוטים; שרת ציבורי ושירות מייל עדיין אינם מוגדרים.
