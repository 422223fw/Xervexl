# World and mode workshop

Open **WORLD WORKSHOP**. Choose a biome and an object type. Click in the overhead map to place objects and right click to erase. Size/height buttons affect the next placement. Leave walking space between objects. Choose 8, 20, 40 or 100 fighters and a compatible team size, then survival or respawns.

Click the code pane to program events. Enter adds a line; Ctrl+A selects all code and Ctrl+V pastes. **SAVE WORLD** validates and saves the map/code, and **PLAY SAVED WORLD** opens its actual authoritative arena. Sign in is required to save/play. The mode catalog also lists saved worlds. Only the creator can overwrite their world.

```text
# Start with a bow, reward precise eliminations, and help your rescuer.
on start weapon bow
on kill if head score 50
on revive if low_health heal 25
on revive stamina 40
on win xp 500
on win coins 200
```

Each instruction has this grammar:

```text
on EVENT [if CONDITION] ACTION VALUE
```

| Part | Accepted values |
|---|---|
| EVENT | `start`, `kill`, `down`, `revive`, `win` |
| CONDITION | `head` (event hit region), `low_health` (actor below 40% max health) |
| ACTION | `heal`, `stamina`, `score`, `xp`, `coins`, `weapon` |
| VALUE | Integer 0–1000, or an existing weapon ID for `weapon` |

Weapon examples include `knife`, `arming`, `longsword`, `spear`, `bow`, `crossbow`, `stormblade` and `emberstaff`. A custom starting weapon is temporary and does not grant permanent ownership. `heal`/`stamina` respect current maximums. `score`/`xp`/`coins` are visible match counters. Kill refills happen before the kill event, so healing on revive is usually more useful than healing after a kill.

Scripts contain up to 48 instructions / 4,096 characters; blank lines and `#` comments are allowed. There are no loops, imports, filesystem/network access or arbitrary Python/Lua calls. Invalid lines report their line number. This is a deliberately small event programming language, not general game-engine scripting or a weapon/asset importer.

Workshop modes are **unranked**. Scripted XP/crowns and custom combat progress never change the persistent account economy or official leaderboards. Official modes provide permanent XP, crowns and skill rewards. Map/code data is stored in private `data/accounts.workshop.json` beside the server's account files. The editor runs locally; sharing a server requires a reachable host. A running match keeps its geometry until another instance/round is created.
