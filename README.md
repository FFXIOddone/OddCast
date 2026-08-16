# OddCast

OddCast is a small Ashita v4 addon for explicit, one-command elemental spell
selection. It includes a native settings window, while casting remains fully
manual: there is no automatic rotation and no packet injection.

## Requirements

- Ashita v4
- a supported FFXI client build with the validated Vana'diel-time layout

For a packaged release, verify `OddCast-v1.1.1.zip` against `SHA256SUMS.txt`,
then extract its `oddcast` directory into `Ashita\addons`. For a source install,
copy the complete `addons\oddcast` directory to `Ashita\addons\oddcast`.

The installed directory must contain exactly `oddcast.lua`, `weakness_data.lua`,
`weakness_data_manifest.json`, `README.md`, `THIRD_PARTY_NOTICES.md`,
`LICENSE-LUASHITACAST-MIT`, and `LICENSE-ODDCAST-GPL-3.0`. Then run:

```text
/addon load oddcast
```

## Commands

```text
/oddcast day
/oc day
/oddcast day [SERVER_ID]
/oc day [SERVER_ID]
/oddcast weakness
/oc weak
/oddcast weakness [SERVER_ID]
/oc weak [SERVER_ID]
/oc settings
/oc target
/oc target <t>
/oc target <bt>
/oc tier
/oc tier day <1-5|I-V|clear>
/oc tier weak <1-5|I-V|clear>
/oc chat
/oc chat <on|off>
/oc help
```

`settings` opens OddCast's native Ashita settings window and also prints the
current values in chat. The window controls `<t>` versus `<bt>`, the independent
Day and Weakness/fallback tier ceilings, routine chat feedback, and a one-click
reset to safe defaults.
Changes apply immediately only after OddCast saves, reloads, and verifies the
value through Ashita's settings API. A failed read-back reports an error and
restores the prior value when Ashita's persistence API remains available.
Close the window with its normal X; all text commands remain available as a
fallback.

Routine automatic chat is off by default. `/oc chat on` enables cast submission,
confirmation, queue, cast-bar, and load status messages; `/oc chat off` hides
them again. Actionable errors, `/oc help`, setting queries, and setting-change
confirmations remain visible either way. The same setting is available as
`Show routine chat messages` in the settings window and is persisted per
character.

To make every receiving character use the sender's selected monster, send the
command through MultiSend:

```text
/ms send /oc day [t]
/ms send /oc weak [t]
```

MultiSend resolves `[t]` on the sending character and replaces it with that
target's decimal server ID before OddCast receives the command. OddCast treats
that ID as a one-shot target; it does not change or save the receiver's
`<t>`/`<bt>` setting. A direct `/oc weak [t]` is invalid because `[t]` must be
expanded by MultiSend first. The resolved monster must be visible to each
receiving client in the same zone.

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

`tier` controls independent ceilings for `day` and `weak`. Both default to V.
For example, `/oc tier day III` limits only day selection to tiers I-III, while
`/oc tier weak 4` limits recognized weaknesses and the unknown-target fallback
to tiers I-IV. Arabic `1`-`5` and Roman `I`-`V` inputs are accepted
case-insensitively. `/oc tier`, `/oc tier day`, `/oc tier weak`, and
`/oc settings` report the persisted values. Use `clear` in place of a tier to
restore that mode's default ceiling of V.

If the player is already casting, OddCast keeps exactly one pending request for
up to 15 seconds instead of sending a command that FFXI will reject as busy. It
briefly checks that an initially positive cast-bar count is actually moving, so
the frozen count left by an interrupted cast is recognized as stale idle within
0.10 seconds. A genuinely moving cast retains the full behavior: OddCast waits
for the cast bar to clear plus a 3.1-second post-cast settle, rechecks the
same target identity, recalculates the highest ready spell, and submits a normal
`/ma` command. OddCast retains the request until the player's incoming action
packet confirms that exact spell started; an unconfirmed submission is retried
at most four times inside the same 15-second bound. A newer `/oc day` or
`/oc weak` replaces the not-yet-submitted intent; any already-submitted attempt
remains the sole in-flight cast until it starts or its retry lock ends. A target
identity change, a target-setting change for a request that used the setting,
expiry, ambiguous cast start, or addon unload cancels it. One-shot server-ID
requests remain bound to their captured target even if `<t>` or `<bt>` changes.
This is bounded completion of an explicit command, not an automatic rotation.

`target` controls the hostile-target token used by both cast commands. The
default is `<t>`; `<bt>` selects Ashita's current battle target. `/oc target`
and `/oc settings` report the current value. The setting is persisted through
Ashita's native settings system. Only `<t>` and `<bt>` are accepted because
deferred subtarget tokens could let the player choose a different monster after
OddCast has already selected a spell. An active subtarget cursor makes `<t>`
fail closed; finish or cancel it before using OddCast.

Missing or invalid settings, targets, spell resources, job levels, MP, recast
data, Vana time, the weakness index, or the chat command queue all fail closed
and submit nothing. OddCast resolves the configured token or one-shot server ID
first, then rechecks the same target's zone, index, server ID, and name
immediately before either command is submitted. Normal FFXI checks still decide
whether the queued command executes; OddCast does not claim the caster remained
in range or unsilenced when the client later executes it.

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

A clean-worktree release is built and then reproduced byte-for-byte with:

```text
python tools/build_release.py --expect-version 1.1.1 --output build/release/v1.1.1
python tools/build_release.py --expect-version 1.1.1 --output build/release/v1.1.1 --check
```

The builder uses a fixed seven-file allowlist and produces the ZIP,
`MANIFEST.json`, and `SHA256SUMS.txt`. `--allow-dirty` exists only for local
development tests and records that state in the manifest; do not distribute
such an artifact as an official release.

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
