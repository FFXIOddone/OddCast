# Third-party notices

## LuAshitacast

OddCast's read-only Vana'diel-time lookup -- the `FFXiMain.dll` byte signature,
the `+0x34` / `+0x0C` relative pointer chain, epoch offset `92514960`, and
day length `3456` -- was adapted from LuAshitacast.

- Upstream: <https://github.com/ThornyFFXI/LuAshitacast>
- Reference revision: `e4a391815722bbb84c802f87a1bc66568fc6e2fd`
- Relevant upstream files: `state.lua` and `data.lua`
- License: MIT
- Copyright: Copyright (c) 2021 ThornyFFXI
- Bundled license text: `LICENSE-LUASHITACAST-MIT`

No affiliation with or endorsement by LuAshitacast or ThornyFFXI is implied.

### MIT License

MIT License

Copyright (c) 2021 ThornyFFXI

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## FancyChat battle-target resolver

OddCast's exact `<bt>` identity resolver -- the `SeekBattleActor` function
signature, `XiAtelBuff` / character-ID FFI layout, and the associated
`FFXiMain.dll` byte signature -- was adapted from FancyChat's `targets.lua`.

- Ashita project: <https://www.ashitaxi.com/>
- Immediate source reviewed: installed FancyChat `targets.lua`
- FancyChat author: Arielfy
- Source copyright: Copyright (c) 2024 Ashita Development Team
- License: GPL-3.0-or-later
- Bundled license text: `LICENSE-ODDCAST-GPL-3.0`
- Installed source SHA-256 reviewed: `1ff17392b66b573c77bf2db3ceedc6fd444e4b9eb12bf9dc7d3e839794c6209c`

OddCast's `oddcast.lua` is consequently distributed under
GPL-3.0-or-later. No affiliation with or endorsement by FancyChat, Arielfy, or
the Ashita Development Team is implied.

## CatsEyeXI/LandSandBoat-derived weakness data

`weakness_data.lua` and `weakness_data_manifest.json` are generated from
monster spawn, pool, family, resistance, spell-formula, and enum metadata in
the CatsEyeXI/LandSandBoat server source.

- Upstream: <https://github.com/CatsAndBoats/catseyexi>
- Contributors: CatsEyeXI/LandSandBoat contributors
- Source commit: `4cf9796860e4a1fd338df15ee9b45406678400b9`
- Data license: GPL-3.0-or-later
- Bundled license text: `LICENSE-ODDCAST-GPL-3.0`

The generated table and manifest embed an aggregate SHA-256 identity for every
material input used by the generator.
