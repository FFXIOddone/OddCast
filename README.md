# OddCast

OddCast is a small Ashita v4 addon for explicit, one-command elemental spell
selection. It is text-command only: there is no GUI, no automatic casting
rotation, and no packet injection.

## Requirements

- Ashita v4
- a supported FFXI client build with the validated Vana'diel-time layout

Copy the complete `addons\oddcast` directory to `Ashita\addons\oddcast`. The
installed copy must include `oddcast.lua`, `weakness_data.lua`,
`THIRD_PARTY_NOTICES.md`, `LICENSE-LUASHITACAST-MIT`, and
`LICENSE-ODDCAST-GPL-3.0`. Then run:

```text
/addon load oddcast
```

## Commands

```text
/oddcast day
/oc day
/oddcast weakness
/oc weak
/oc settings
/oc target
/oc target <t>
/oc target <bt>
/oc help
```

`day` reads the client's current Vana'diel day and queues the highest modeled
ready single-target spell of that element. For the six standard tier lines,
base power rises with tier, so this selects the highest available tier.

`weak` looks up the target's normalized mob name in one global CatsEye-derived
table, with typical family prefixes as a fallback. It is independent of zone:
a Damselfly uses the Fly profile everywhere and an ordinary Goblin uses the
Goblin profile everywhere. When source variants disagree, the most common
profile wins; the lowest profile ID breaks an exact vote tie. OddCast chooses
the available element with the best resistance rank, then the strongest
`base power * elemental SDT` spell within that rank.

When a custom mob has no exact name or family match, `weak` falls back to the
strongest modeled ready spell across the six comparable elemental tier lines.
Missing or malformed weakness data still fails closed rather than bypassing
the validated catalog.

Ready means all of the following are true: the spell is learned, the current
main or subjob can use it at its current level, current MP covers its cost, and
its recast is zero.

If the player is already casting, OddCast keeps exactly one pending request for
up to 15 seconds instead of sending a command that FFXI will reject as busy. It
waits for the cast bar to clear plus a 0.5-second post-cast settle, rechecks the
same target identity, recalculates the highest ready spell, and submits a normal
`/ma` command. OddCast retains the request until the player's incoming action
packet confirms that exact spell started; an unconfirmed submission is retried
at most four times inside the same 15-second bound. A newer `/oc day` or
`/oc weak` replaces the not-yet-submitted intent; any already-submitted attempt
remains the sole in-flight cast until it starts or its retry lock ends. A target or target-setting change,
expiry, ambiguous cast start, or addon unload cancels it. This is bounded
completion of an explicit command, not an automatic rotation.

`target` controls the hostile-target token used by both cast commands. The
default is `<t>`; `<bt>` selects Ashita's current battle target. `/oc target`
and `/oc settings` report the current value. The setting is persisted through
Ashita's native settings system. Only `<t>` and `<bt>` are accepted because
deferred subtarget tokens could let the player choose a different monster after
OddCast has already selected a spell. An active subtarget cursor makes `<t>`
fail closed; finish or cancel it before using OddCast.

Missing or invalid settings, targets, spell resources, job levels, MP, recast
data, Vana time, the weakness index, or the chat command queue all fail closed
and submit nothing. OddCast resolves the configured token first, then rechecks the
same token's zone, target index, server ID, and target name immediately before
either command is submitted. Normal FFXI checks still decide whether the queued
command executes; OddCast does not claim the caster remained in range,
unsilenced, or on the same target when the client later executes the token.

The displayed result is a **typical family baseline**, not an actual damage
prediction. The one generated table records its pinned CatsEye source SHA-256;
offline validation checks its hash, schema, names, family prefixes, profiles,
and deterministic ambiguity counts. Live INT/MEVA, buffs, gear, day/weather,
status, range, and special scripted behavior remain outside this simple model.

Weakness selection remains limited to the six standard single-target INT tier
lines. AoE, ancient magic, divine/light, helix damage-over-time, Drain, and
differently scaled spell families are not compared. Light and dark day commands
can still use a ready direct light/dark spell, with Drain as a Darksday fallback.

## Third-party attribution

OddCast determines the Vana'diel-time location at runtime by scanning
`FFXiMain.dll` for a byte signature and following relative pointer offsets; it
does not contain a fixed absolute process address. That read-only signature,
pointer chain, epoch offset, and day-length calculation were adapted from
[LuAshitacast](https://github.com/ThornyFFXI/LuAshitacast) by ThornyFFXI under
the MIT License. LuAshitacast is an implementation source, not an OddCast
runtime dependency. No affiliation with or endorsement by LuAshitacast or
ThornyFFXI is implied. The complete copyright and permission notice is bundled
in `addons/oddcast/THIRD_PARTY_NOTICES.md` and
`addons/oddcast/LICENSE-LUASHITACAST-MIT`.

OddCast's exact `<bt>` identity resolver uses a function signature and FFI
actor layout adapted from FancyChat's `targets.lua`, as distributed with the
[Ashita](https://www.ashitaxi.com/) installation reviewed for this release.
That source is copyright (c) 2024 Ashita Development Team and licensed under
GPL-3.0-or-later; FancyChat is authored by Arielfy.
OddCast is not affiliated with or endorsed by FancyChat, Arielfy, or the Ashita
Development Team. Full details and license text are bundled with the addon.

## Offline validation

Development checks require Python 3.10 or newer, `pytest`, and a `luajit`
executable on `PATH`:

```text
python -m pytest tests -q -p no:cacheprovider
python tools/build_weakness_data.py --validate-output --luajit <path-to-luajit>
luajit -b addons/oddcast/oddcast.lua oddcast.luac
```

The optional CatsEye source-parity test is skipped when a sibling CatsEye
server checkout is unavailable. Set `CATSEYE_SERVER_ROOT` to run that check
against an explicit checkout. Maintainers regenerate and byte-validate the
global mob table with:

```text
python tools/build_weakness_data.py --server-root <path-to-catseyexi> --luajit <path-to-luajit>
python tools/build_weakness_data.py --server-root <path-to-catseyexi> --check
```

The generator joins active spawns to pools, families, and resistance profiles,
then selects the typical profile for each normalized mob name and family label.
The checked-in manifest binds the source commit, material-input hash, generator
hash, table hash, counts, and ambiguity totals. These checks do not install the
addon or issue game commands. Personal-use testing can be performed in your own
client; distribution remains subject to the server's addon approval policy.

## Licensing

`addons/oddcast/oddcast.lua` is GPL-3.0-or-later because its `<bt>` resolver
adapts GPL-licensed FancyChat code. OddCast's separately authored Python
tooling and tests remain MIT licensed under the repository-root `LICENSE`.
The generated `weakness_data.lua` and `weakness_data_manifest.json` are derived
from the pinned CatsEye server source and are GPL-3.0-or-later. See
`THIRD_PARTY_NOTICES.md`, `LICENSE-DATA-GPL-3.0`,
`addons/oddcast/LICENSE-ODDCAST-GPL-3.0`, and
`LICENSE-LUASHITACAST-MIT`.
