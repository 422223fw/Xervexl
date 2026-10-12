# Xervexl — motlon

A playable Windows sword arena prototype with native C++ rendering in **OpenGL or Vulkan**, an authoritative Python server, persistent equipment, and bots that fill empty player slots. Original procedural scenery and characters: daylight, sand, stone walls, banners, trees, steel and shields. No supernatural abilities, match winner or final round.

## Play

Double-click **Play-Xervexl.cmd**. It starts a hidden local arena server and opens the game. No Windows administrator privileges are needed. Python 3.10+ is required; Python and the portable C++ compiler are already installed on this computer.

The compiled game is `build/Xervexl.exe`. For Vulkan, choose **Settings → Vulkan**, or run `powershell -NoProfile -ExecutionPolicy Bypass -File start.ps1 -Vulkan`. A compatible GPU driver is required; the client reports failure and falls back to OpenGL.

**Enter the arena** works immediately as a guest. Sign in or create an account to keep equipment and crowns. Guests start with a knife and 100 crowns; registered accounts also start with a knife and 100 crowns. Defeating a fighter earns 45 crowns. New purchases equip automatically. Guest progress is temporary.

| Control | Action |
|---|---|
| W / A / S / D | Move |
| Mouse | Turn and look |
| Left mouse button | Attack with selected move |
| 1 / 2 / 3 / 4 | Left cut / right cut / overhead / thrust |
| Right mouse button | Block facing an attack |
| Right mouse just before impact | Timed parry; 180 ms window |
| Shift | Short dodge, costs stamina |
| Space | Low jump, costs stamina |
| E | Armoury |
| Escape | Menu / resume; online combat keeps running |
| F12 | Save game-frame screenshot in `screenshots/capture.bmp` |

Overhead attacks cost more stamina and recover more slowly. Thrusts have extra reach and a narrow hit cone but lower damage. Shields improve ordinary blocks; armour reduces damage, and plate slows movement. Dodges briefly evade strikes. Death returns you to the arena after 3.5 seconds. New spawns have a 1.5-second entry grace during which they neither deal nor receive damage.

## Multiplayer

The server supplies enough bots to keep **at least ten total combatants**. When ten humans are connected, it removes all filler bots. Bot skill depths are shuffled among 2, 3, 4 and 5. Two native clients can fight in the same authoritative arena, including clients using different graphics APIs.

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

Smoke tests: `build/Xervexl.exe --smoke`, `--smoke --vulkan`, `--smoke --arena`, and `--smoke --arena --vulkan`. They run four seconds, save renderer reports and **GPU-frame** screenshots, then leave the arena. `--shop` opens the armoury for visual checking. Tests cover account hashing/persistence, equipment, authority, timed parry, damage, respawn, bot filling, and a simulation guarding against bots endlessly postponing attacks.

## Prototype limits

This is the first playable build, not a finished commercial game or a photorealistic production. The arena has a finite physical boundary and continuous play; it does **not** support literally infinite simultaneous people. There is no measured large-scale player capacity. Each server currently has one arena, and collision checks scale quadratically with population. There is no public hosting, matchmaking directory, moderation, account email verification, server deployment automation or production anti-cheat service.

Bot search really runs 2–5 plies with a seven-state beam, but uses a simplified combat forecast and a nearest-opponent target. It is not full chess-style optimal play or a general model of human reasoning. Combat uses distance/angle hit cones and capsule-like player separation, not per-bone weapon collisions. Jumping is small and visual; it is not an extra invulnerability power. The third-person camera can pass through scenery.

3D geometry is projected on the CPU and triangles are sorted before drawing. OpenGL uses a fixed-function triangle stream; Vulkan uses a real instance/device, swapchain, command buffers, vertex buffer, SPIR-V graphics pipeline and GPU presentation. There is no GPU depth buffer, advanced lighting, textures, animation skeleton, positional audio or modern postprocessing yet. The initial graphics are procedural and stylized.

The local server is a threaded Python HTTP prototype with atomic private JSON storage and rate limiting on account requests. Internet production requires hosting, HTTPS, hardened operations and load testing. Reset mail delivery requires your SMTP service. Source files alone in GitHub are not a running online game.

## Third-party components

See `THIRD_PARTY.md`. Art and short combat sounds are generated by the project. No Saber Showdown assets or code are included.

## הוראות קצרות

לחצי פעמיים על **Play-Xervexl.cmd**, ואז **Enter the arena**. לתנועה: WASD ועכבר. לתקיפה: לחיצה שמאלית; 1–4 בוחרים מהלך. לחיצה ימנית חוסמת, Shift מתחמק ו־Space קופץ מעט. E פותח את החנות. להרשמה ושמירת ציוד: Sign in ואז Create account. המשחק עובד מקומית עם בוטים; שרת ציבורי ושירות מייל עדיין אינם מוגדרים.
