# OddCast

OddCast is a small Ashita v4 addon for explicit, one-command elemental spell
selection. It never casts in the background and never injects packets.

## Requirements

- Ashita v4
- a current LuAshitacast-compatible FFXI client (OddCast uses the same validated
  Vana time signature)

Copy `addons\oddcast` to `Ashita\addons\oddcast`, then run:

```text
/addon load oddcast
```

## Commands

```text
/oddcast day
/oc day
/oddcast weakness
/oc weak
/oc help
```

`day` reads the client's current Vana'diel day and queues the highest modeled
ready single-target spell of that element. For the six standard tier lines,
base power rises with tier, so this selects the highest available tier.

`weak` is deliberately disabled in version 0.1.1. The installed MobDB files
use legacy elemental modifiers that are not validated against current CatsEye
resistance semantics and can recommend the wrong element. `/oc weak` therefore
prints a concrete explanation and queues nothing.

Ready means all of the following are true: the spell is learned, the current
main or subjob can use it at its current level, current MP covers its cost, and
its recast is zero. `day` requires a selected monster and queues one ordinary
`/ma "Spell" <t>` client command.

Missing targets, spell resources, job levels, MP, recast data, Vana time, or
the chat command queue all fail closed and queue nothing. Normal FFXI checks
still decide whether the queued command executes; OddCast rechecks target
identity immediately before the queue call, but does not claim the caster
remained in range, unsilenced, or on the same target when the client later
executes `<t>`.

The planned weakness implementation will use a generated exact target-ID table
and fail closed for ambiguous or dynamically modified targets. It will remain
limited to the six standard single-target INT tier lines; AoE, ancient magic,
divine/light, helix damage-over-time, Drain, and differently scaled spell
families are not safely comparable as one static choice. Light and dark day
commands can still use a ready direct light/dark spell, with Drain as a
Darksday fallback.

## Offline validation

Development checks require Python 3.10 or newer, `pytest`, and a `luajit`
executable on `PATH`:

```text
python -m pytest tests/test_oddcast_addon.py -q -p no:cacheprovider
luajit -b addons/oddcast/oddcast.lua oddcast.luac
```

The optional CatsEye source-parity test is skipped when a sibling CatsEye
server checkout is unavailable. These checks do not install the addon or issue
game commands. Runtime testing belongs in a private or explicitly approved
test environment.
