# OddCast

OddCast is a small Ashita v4 addon for explicit, one-command elemental spell
selection. It is text-command only: there is no GUI, it never casts in the
background, and it never injects packets.

## Requirements

- Ashita v4
- a current LuAshitacast-compatible FFXI client (OddCast uses the same validated
  Vana time signature)

Copy the complete `addons\oddcast` directory to `Ashita\addons\oddcast`. The
installed copy must include `oddcast.lua`, `weakness_data.lua`, and every
generated `weakness_data\<zone>.lua` file. Then run:

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

`weak` uses generated CatsEye static resistance data for the exact target's
zone, target index, server ID, and display name. It picks the highest ready
spell in each of the six standard elemental tier lines, then compares each
candidate's `base power * clamp(10000 + elemental SDT, 0, 30000)` baseline and
resistance rank. Lower rank is better. A spell is queued only when one
candidate is no worse on both measures and strictly better on at least one
measure than every other candidate. Ties and potency/rank tradeoffs fail closed.

Ready means all of the following are true: the spell is learned, the current
main or subjob can use it at its current level, current MP covers its cost, and
its recast is zero.

`target` controls the hostile-target token used by both cast commands. The
default is `<t>`; `<bt>` selects Ashita's current battle target. `/oc target`
and `/oc settings` report the current value. The setting is persisted through
Ashita's native settings system. Only `<t>` and `<bt>` are accepted because
deferred subtarget tokens could let the player choose a different monster after
OddCast has already selected a spell. An active subtarget cursor makes `<t>`
fail closed; finish or cancel it before using OddCast.

Missing or invalid settings, targets, spell resources, job levels, MP, recast
data, Vana time, weakness data, or the chat command queue all fail closed and
queue nothing. OddCast resolves the configured token first, then rechecks the
same token's zone, target index, server ID, and target name immediately before
either command is queued. Normal FFXI checks still decide whether the queued
command executes; OddCast does not claim the caster remained in range,
unsilenced, or on the same target when the client later executes the token.

The displayed result is a **static baseline recommendation**, not an actual
damage prediction. The generated index records its pinned CatsEye source
SHA-256 and the expected SHA-256 of each split zone file; offline validation
checks those file hashes. The Ashita runtime validates matching schemas, source
identity, zone metadata, record counts, and exact target identity, but has no
built-in SHA-256 implementation and therefore does not hash files in-game.
Live INT/MEVA, buffs, gear, day/weather, status, range, and runtime-scripted
resistance changes remain outside this static model. Targets without a safe
static record must be omitted by the data generator and fail closed at runtime.

Weakness selection remains limited to the six standard single-target INT tier
lines. AoE, ancient magic, divine/light, helix damage-over-time, Drain, and
differently scaled spell families are not compared. Light and dark day commands
can still use a ready direct light/dark spell, with Drain as a Darksday fallback.

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
split target data with:

```text
python tools/build_weakness_data.py --server-root <path-to-catseyexi> --luajit <path-to-luajit>
python tools/build_weakness_data.py --server-root <path-to-catseyexi> --check
```

The generator uses the exact spawn-to-group-to-pool-to-resistance join. It
omits inactive or incomplete rows, direct scripted mobs, zones with automatic
mixins, and pools or species with magic-affecting modifier overrides. The
checked-in manifest partitions every source spawn into one included or excluded
reason and binds the exact source commit, material-input hash, generator hash,
per-file hashes, counts, and inventory. These checks do not install the addon
or issue game commands. Personal-use testing can be performed in your own
client; distribution remains subject to the server's addon approval policy.

## Licensing

OddCast's handwritten addon and tooling are MIT licensed. The generated
`weakness_data.lua`, `weakness_data_manifest.json`, and
`weakness_data\*.lua` files are derived from the pinned CatsEye server source
and are GPL-3.0-or-later. See `THIRD_PARTY_NOTICES.md` and
`LICENSE-DATA-GPL-3.0`.
