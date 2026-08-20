from pathlib import Path
import os
import re
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
ODDCAST_PATH = ROOT / "addons" / "oddcast" / "oddcast.lua"
ODDCAST_DIR = ODDCAST_PATH.parent
LOCALES_PATH = ODDCAST_DIR / "locales.lua"
CATSEYE_SERVER_ROOT = Path(
    os.environ.get("CATSEYE_SERVER_ROOT", ROOT.parent / "server")
)
CATSEYE_DAMAGE_SPELL_PATH = (
    CATSEYE_SERVER_ROOT / "scripts" / "globals" / "spells" / "damage_spell.lua"
)
CATSEYE_MAGIC_ENUM_PATH = CATSEYE_SERVER_ROOT / "scripts" / "enum" / "magic.lua"


def _weakness_catalog_rows() -> list[tuple[str, str, str, str, str]]:
    addon_text = ODDCAST_PATH.read_text(encoding="utf-8")
    return re.findall(
        r"\{\s*id=(\d+),\s*name='([^']+)',\s*element='([^']+)',"
        r"\s*tier=(\d+),\s*power=(\d+),\s*weak=true\s*\}",
        addon_text,
    )


def test_oddcast_metadata_credits_oddone() -> None:
    addon_text = ODDCAST_PATH.read_text(encoding="utf-8")
    assert "addon.author = 'Oddone';" in addon_text
    assert "addon.author = 'OddLua';" not in addon_text


def test_luashitacast_vana_time_adaptation_has_complete_attribution() -> None:
    addon_text = ODDCAST_PATH.read_text(encoding="utf-8")
    readme_texts = (
        (ROOT / "README.md").read_text(encoding="utf-8"),
        (ODDCAST_DIR / "README.md").read_text(encoding="utf-8"),
    )
    notice_texts = (
        (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8"),
        (ODDCAST_DIR / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8"),
    )
    license_texts = (
        (ROOT / "LICENSE-LUASHITACAST-MIT").read_text(encoding="utf-8"),
        (ODDCAST_DIR / "LICENSE-LUASHITACAST-MIT").read_text(encoding="utf-8"),
    )

    provenance = (
        "-- Provenance: Vana'diel-time signature and relative pointer-chain constants were\n"
        "-- adapted from LuAshitacast by ThornyFFXI (MIT). See THIRD_PARTY_NOTICES.md."
    )
    provenance_index = addon_text.index(provenance)
    signature_index = addon_text.index("local VANA_TIME_SIGNATURE")
    assert 0 < signature_index - provenance_index < 300
    assert "addon.version = '1.3.0';" in addon_text

    for text in readme_texts + notice_texts:
        assert "https://github.com/ThornyFFXI/LuAshitacast" in text
        assert "ThornyFFXI" in text
        assert "MIT License" in text

    assert license_texts[0] == license_texts[1]
    for token in (
        "Copyright (c) 2021 ThornyFFXI",
        "Permission is hereby granted, free of charge",
        "The above copyright notice and this permission notice shall be included",
        'THE SOFTWARE IS PROVIDED "AS IS"',
    ):
        for text in notice_texts + license_texts:
            assert token in text
    for notice_text in notice_texts:
        assert "e4a391815722bbb84c802f87a1bc66568fc6e2fd" in notice_text
        assert license_texts[0].strip() in notice_text


def test_fancychat_battle_target_adaptation_has_complete_attribution() -> None:
    addon_text = ODDCAST_PATH.read_text(encoding="utf-8")
    readme_texts = (
        (ROOT / "README.md").read_text(encoding="utf-8"),
        (ODDCAST_DIR / "README.md").read_text(encoding="utf-8"),
    )
    notice_texts = (
        (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8"),
        (ODDCAST_DIR / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8"),
    )
    gpl_text = (ODDCAST_DIR / "LICENSE-ODDCAST-GPL-3.0").read_text(
        encoding="utf-8"
    )
    canonical_gpl_text = (ROOT / "LICENSE-DATA-GPL-3.0").read_text(
        encoding="utf-8"
    )

    provenance = (
        "-- Provenance: <bt> signature and FFI actor layout adapted from FancyChat's\n"
        "-- targets.lua (Ashita Development Team, GPL-3.0-or-later). See THIRD_PARTY_NOTICES.md."
    )
    provenance_index = addon_text.index(provenance)
    signature_index = addon_text.index("local BATTLE_TARGET_SIGNATURE")
    assert 0 < signature_index - provenance_index < 300
    assert addon_text.startswith("-- SPDX-License-Identifier: GPL-3.0-or-later\n")
    assert "-- Modified for OddCast on 2026-08-12; see THIRD_PARTY_NOTICES.md." in addon_text
    assert gpl_text == canonical_gpl_text

    for text in readme_texts + notice_texts:
        assert "https://www.ashitaxi.com/" in text
        assert "Ashita Development Team" in text
        assert "GPL-3.0-or-later" in text
        assert "FancyChat" in text
    for notice_text in notice_texts:
        assert "Arielfy" in notice_text
        assert "1ff17392b66b573c77bf2db3ceedc6fd444e4b9eb12bf9dc7d3e839794c6209c" in notice_text
    assert "GNU GENERAL PUBLIC LICENSE" in gpl_text
    for text in readme_texts + notice_texts:
        assert "OddCast's handwritten addon and tooling are MIT licensed" not in text
        assert "handwritten addon and tooling remain" not in text


def test_catseye_weakness_data_notice_ships_with_the_addon() -> None:
    notice_text = (ODDCAST_DIR / "THIRD_PARTY_NOTICES.md").read_text(
        encoding="utf-8"
    )
    for token in (
        "CatsEyeXI/LandSandBoat-derived weakness data",
        "https://github.com/CatsAndBoats/catseyexi",
        "CatsEyeXI/LandSandBoat contributors",
        "4cf9796860e4a1fd338df15ee9b45406678400b9",
        "GPL-3.0-or-later",
        "LICENSE-ODDCAST-GPL-3.0",
    ):
        assert token in notice_text


def test_oddcast_day_table_is_complete_and_in_vana_week_order() -> None:
    addon_text = ODDCAST_PATH.read_text(encoding="utf-8")
    rows = re.findall(
        r"\{ day = '([^']+)', element = '([^']+)' \}", addon_text
    )
    assert rows == [
        ("Firesday", "Fire"),
        ("Earthsday", "Earth"),
        ("Watersday", "Water"),
        ("Windsday", "Wind"),
        ("Iceday", "Ice"),
        ("Lightningday", "Lightning"),
        ("Lightsday", "Light"),
        ("Darksday", "Dark"),
    ]
    assert "local VANA_TIME_EPOCH_OFFSET = 92514960" in addon_text
    assert "local VANA_DAY_SECONDS = 3456" in addon_text


def test_oddcast_weakness_catalog_is_bounded_to_six_unique_tier_lines() -> None:
    rows = _weakness_catalog_rows()
    assert len(rows) == 30
    assert len({int(row[0]) for row in rows}) == 30
    assert len({row[1] for row in rows}) == 30

    elements = {
        "FIRE": "Fire",
        "BLIZZARD": "Ice",
        "AERO": "Wind",
        "STONE": "Earth",
        "THUNDER": "Lightning",
        "WATER": "Water",
    }
    tiers = {"": 1, "II": 2, "III": 3, "IV": 4, "V": 5}
    for _spell_id, name, element, tier, _power in rows:
        symbol = name.upper().replace(" ", "_")
        family, _, suffix = symbol.partition("_")
        assert element == elements[family], name
        assert int(tier) == tiers[suffix], name

    addon_text = ODDCAST_PATH.read_text(encoding="utf-8")
    assert "Luminohelix" not in addon_text
    assert "Noctohelix" not in addon_text


def test_oddcast_light_and_dark_day_families_are_dia_and_bio_only() -> None:
    addon_text = ODDCAST_PATH.read_text(encoding="utf-8")
    day_rows = re.findall(
        r"\{\s*id=(\d+),\s*name='([^']+)',\s*element='(Light|Dark)',"
        r"\s*tier=(\d+),\s*power=(\d+),\s*weak=false\s*\}",
        addon_text,
    )
    assert day_rows == [
        ("23", "Dia", "Light", "1", "1"),
        ("24", "Dia II", "Light", "2", "4"),
        ("25", "Dia III", "Light", "3", "16"),
        ("230", "Bio", "Dark", "1", "10"),
        ("231", "Bio II", "Dark", "2", "50"),
        ("232", "Bio III", "Dark", "3", "100"),
    ]
    for excluded in ("Banish", "Holy", "Comet", "Drain"):
        assert f"name='{excluded}" not in addon_text


@pytest.mark.skipif(
    not CATSEYE_DAMAGE_SPELL_PATH.is_file() or not CATSEYE_MAGIC_ENUM_PATH.is_file(),
    reason="requires the sibling CatsEye server checkout for source parity",
)
def test_oddcast_weakness_catalog_matches_catseye_pc_base_power_table() -> None:
    rows = _weakness_catalog_rows()
    server_text = CATSEYE_DAMAGE_SPELL_PATH.read_text(encoding="utf-8")
    enum_text = CATSEYE_MAGIC_ENUM_PATH.read_text(encoding="utf-8")
    spell_enum_text = enum_text.split("xi.magic.spell =", maxsplit=1)[1]

    for spell_id, name, _element, _tier, power in rows:
        symbol = name.upper().replace(" ", "_")
        enum_row = re.search(
            rf"^\s*{symbol}\s*=\s*(\d+),", spell_enum_text, re.MULTILINE
        )
        assert enum_row is not None, name
        assert int(spell_id) == int(enum_row.group(1)), name
        server_row = re.search(
            rf"\[xi\.magic\.spell\.{symbol}\s*\]\s*=\s*\{{"
            r"\s*xi\.mod\.[A-Z]+,\s*[^,]+,\s*[^,]+,\s*[^,]+,\s*([^,]+),",
            server_text,
        )
        assert server_row is not None, name
        assert float(power) == float(server_row.group(1)), name


def test_oddcast_day_command_and_missing_weakness_data_are_fail_closed(tmp_path: Path) -> None:
    luajit = shutil.which("luajit")
    assert luajit is not None
    assert ODDCAST_PATH.is_file()

    driver = tmp_path / "oddcast_contract.lua"
    driver.write_text(
        "\n".join(
            (
                "local ODDCAST_PATH = [[" + ODDCAST_PATH.as_posix() + "]]",
                "local callbacks = {}",
                "local queued = {}",
                "local output = {}",
                "local targetIndex = 321",
                "local targetServerId = 123456",
                "local targetName = 'Proof Rabbit'",
                "local targetZone = 100",
                "local playerServerId = 777777",
                "local now = 100",
                "local castCount = 0",
                "local castbarAvailable = true",
                "local mainJob, mainLevel, subJob, subLevel = 4, 75, 1, 37",
                "local known = { [23]=true, [24]=true, [25]=true, [146]=1, [167]=true, [171]=true, [172]=true, [230]=true, [231]=true, [232]=true }",
                "local timers = {}",
                "local currentMP = 999",
                "local chatAvailable = true",
                "local signatureAddress = 0",
                "local rawTime = (80002 * 3456) - 92514960",
                "local mutateTargetOnTimer = false",
                "local activeSettings = { target='<t>', dayTierCeiling=5, weaknessTierCeiling=5, showRoutineChat=true, language='en' }",
                "local resources = {}",
                "local function spell(id, name, mp, blmLevel)",
                "    resources[id] = { Name={name}, ManaCost=mp, LevelRequired={ [5]=blmLevel } }",
                "end",
                "spell(146, 'Fire III', 63, 62)",
                "spell(167, 'Thunder IV', 195, 75)",
                "spell(171, 'Water III', 46, 55)",
                "spell(172, 'Water IV', 99, 70)",
                "spell(23, 'Dia', 7, 1)",
                "spell(24, 'Dia II', 30, 40)",
                "spell(25, 'Dia III', 45, 75)",
                "spell(230, 'Bio', 15, 1)",
                "spell(231, 'Bio II', 36, 40)",
                "spell(232, 'Bio III', 54, 75)",
                "local originalPrint = print",
                "print = function(value) output[#output + 1] = tostring(value); originalPrint(value) end",
                "T = function(value) return value end",
                "struct = { unpack=function(_, data) return data.actorId end }",
                "package.preload['common'] = function() return true end",
                "package.preload['imgui'] = function() return {} end",
                "package.preload['settings'] = function()",
                "    return { load=function() return activeSettings end, save=function() return true end, register=function() return true end }",
                "end",
                "package.loaded['ffi'] = nil",
                "package.preload['ffi'] = function() return { cdef=function() end, cast=function() error('unexpected <bt> lookup') end } end",
                "package.preload['chat'] = function()",
                "    return { header=function(v) return '['..v..'] ' end, message=function(v) return v end, error=function(v) return v end }",
                "end",
                "addon = { path='fixture/' }",
                "ashita = {",
                "    events = { register=function(name, _, cb) callbacks[name]=cb end },",
                "    memory = {",
                "        find=function() return signatureAddress end,",
                "        read_uint32=function(address)",
                "            if address == 1052 then return 2000 end",
                "            if address == 2012 then return rawTime end",
                "            return 0",
                "        end,",
                "    },",
                "    bits = { unpack_be=function(data, base, offset, length) if base == 10 and offset == 2 and length == 4 then return data.category end if base == 10 and offset == 6 and length == 16 then return data.topLevelParam end if base == 0 and offset == 213 and length == 17 then return data.spellId end error('unexpected packet bit field') end },",
                "}",
                "local target = { GetIsSubTargetActive=function() return 0 end, GetTargetIndex=function() return targetIndex end }",
                "local entity = { GetSpawnFlags=function() return 0x10 end, GetName=function() return targetName end, GetServerId=function() return targetServerId end }",
                "local player = {",
                "    GetMainJob=function() return mainJob end, GetMainJobLevel=function() return mainLevel end,",
                "    GetSubJob=function() return subJob end, GetSubJobLevel=function() return subLevel end,",
                "    HasSpell=function(_, id) return known[id] end,",
                "}",
                "local party = { GetMemberMP=function() return currentMP end, GetMemberZone=function() return targetZone end, GetMemberServerId=function() return playerServerId end }",
                "local recast = { GetSpellTimer=function(_, id)",
                "    if mutateTargetOnTimer then targetIndex=400; targetName='Changed Rabbit'; mutateTargetOnTimer=false end",
                "    return timers[id] or 0",
                "end }",
                "local castbar = { GetCount=function() return castCount end }",
                "local memory = {",
                "    GetTarget=function() return target end, GetEntity=function() return entity end,",
                "    GetPlayer=function() return player end, GetParty=function() return party end,",
                "    GetRecast=function() return recast end, GetCastBar=function() if castbarAvailable then return castbar end return nil end,",
                "}",
                "local resourceManager = { GetSpellById=function(_, id) return resources[id] end }",
                "local chatManager = { QueueCommand=function(_, mode, command) queued[#queued + 1]={mode=mode, command=command} end }",
                "AshitaCore = {",
                "    GetMemoryManager=function() return memory end,",
                "    GetResourceManager=function() return resourceManager end,",
                "    GetChatManager=function() if chatAvailable then return chatManager end return nil end,",
                "}",
                "os.clock = function() return now end",
                "dofile(ODDCAST_PATH)",
                "local function invoke(prefix, action)",
                "    local event={ command={ args=function() return {prefix, action} end }, blocked=false }",
                "    callbacks.command(event)",
                "    assert(event.blocked == true, 'OddCast command was not blocked')",
                "end",
                "local function confirm(spellId)",
                "    callbacks.packet_in({id=0x028, data={actorId=playerServerId}, data_raw={category=8,topLevelParam=0x6163,spellId=spellId}})",
                "end",
                "callbacks.load()",
                "invoke('/oc', 'day')",
                "assert(#queued == 0, 'failed Vana signature scan cast instead of failing closed')",
                "signatureAddress = 1000",
                "invoke('/oc', 'day')",
                "assert(queued[1].mode == 1, 'day did not use the typed command queue')",
                "assert(queued[1].command == '/ma \"Water IV\" <t>', 'day did not choose highest ready Watersday tier')",
                "confirm(172)",
                "local sawConfirmedStart = false",
                "for _, line in ipairs(output) do if string.find(line, 'Confirmed cast start: Water IV.', 1, true) then sawConfirmedStart=true end end",
                "assert(sawConfirmedStart, 'category-8 action spell identity was read from the wrong packet field')",
                "rawTime = 0",
                "invoke('/oc', 'day')",
                "assert(#queued == 1, 'zero Vana time cast instead of failing closed')",
                "rawTime = (80002 * 3456) - 92514960",
                "mainJob, mainLevel, subJob, subLevel = 1, 75, 4, 70",
                "invoke('/oddcast', 'day')",
                "assert(queued[2].command == '/ma \"Water IV\" <t>', 'day rejected a spell available exactly at subjob level')",
                "confirm(172)",
                "subLevel = 69",
                "invoke('/oc', 'day')",
                "assert(queued[3].command == '/ma \"Water III\" <t>', 'day ignored the active subjob level boundary')",
                "confirm(171)",
                "mainJob, mainLevel, subJob, subLevel = 4, 75, 1, 37",
                "timers[172] = 1",
                "invoke('/oc', 'day')",
                "assert(queued[4].command == '/ma \"Water III\" <t>', 'day ignored a higher-tier spell recast')",
                "confirm(171)",
                "timers[172] = nil",
                "currentMP = 50",
                "invoke('/oc', 'day')",
                "assert(queued[5].command == '/ma \"Water III\" <t>', 'day ignored insufficient MP for the higher tier')",
                "confirm(171)",
                "currentMP = 999",
                "mutateTargetOnTimer = true",
                "invoke('/oc', 'day')",
                "assert(#queued == 5, 'target changed during day selection but a spell was queued')",
                "targetIndex = 321",
                "targetName = 'Proof Rabbit'",
                "invoke('/oddcast', 'weak')",
                "assert(#queued == 5, 'missing weakness data queued a spell')",
                "local sawMissing = false",
                "for _, line in ipairs(output) do if string.find(line, 'Weakness index is missing or unreadable', 1, true) then sawMissing=true end end",
                "assert(sawMissing, 'missing weakness data did not explain why')",
                "targetIndex = 0",
                "invoke('/oc', 'weakness')",
                "assert(#queued == 5, 'targetless weakness command queued a spell')",
                "targetIndex = 321",
                "chatAvailable = false",
                "invoke('/oc', 'day')",
                "assert(#queued == 5, 'missing chat manager did not fail closed')",
                "chatAvailable = true",
                "targetIndex = 0",
                "invoke('/oddcast', 'day')",
                "assert(#queued == 5, 'missing target cast instead of failing closed')",
                "local unknown={ command={ args=function() return {'/oc', 'nonsense'} end }, blocked=false }",
                "callbacks.command(unknown)",
                "assert(unknown.blocked == true and #queued == 5, 'unknown OddCast command was not safely consumed')",
                "local extra={ command={ args=function() return {'/oc', 'day', 'typo'} end }, blocked=false }",
                "callbacks.command(extra)",
                "assert(extra.blocked == true and #queued == 5, 'extra command arguments were accepted')",
                "local unrelated={ command={ args=function() return {'/notoddcast', 'day'} end }, blocked=false }",
                "callbacks.command(unrelated)",
                "assert(unrelated.blocked == false, 'unrelated command was blocked')",
                "targetIndex = 321",
                "targetName = 'Proof Rabbit'",
                "castCount = 50",
                "invoke('/oc', 'day')",
                "assert(#queued == 5, 'busy cast request was submitted immediately instead of remaining pending')",
                "assert(callbacks.d3d_present ~= nil, 'pending cast dispatcher was not registered')",
                "now = now + 0.11",
                "castCount = 49",
                "callbacks.d3d_present()",
                "assert(#queued == 5, 'progressing cast-bar count was mistaken for stale idle state')",
                "castCount = 0",
                "now = now + 0.06",
                "callbacks.d3d_present()",
                "assert(#queued == 5, 'pending cast ignored the post-cast lockout')",
                "invoke('/oc', 'day')",
                "assert(#queued == 5, 'repeated command bypassed the inherited post-cast lockout')",
                "now = now + 3.0",
                "callbacks.d3d_present()",
                "assert(#queued == 5, 'pending cast dispatched before the full post-cast lockout')",
                "now = now + 0.2",
                "callbacks.d3d_present()",
                "assert(#queued == 6 and queued[6].command == '/ma \"Water IV\" <t>', 'pending cast did not dispatch after the cast lock cleared')",
                "assert(callbacks.packet_in ~= nil, 'cast-start acknowledgement handler was not registered')",
                "confirm(172)",
                "now = now + 5",
                "callbacks.d3d_present()",
                "assert(#queued == 6, 'confirmed cast start was retried')",
                "castCount = 0",
                "invoke('/oc', 'day')",
                "assert(#queued == 7, 'idle request did not submit its first bounded attempt')",
                "callbacks.packet_in({id=0x028, data={actorId=playerServerId+1}, data_raw={category=8,spellId=172}})",
                "callbacks.packet_in({id=0x028, data={actorId=playerServerId}, data_raw={category=8,spellId=171}})",
                "now = now + 2.1",
                "callbacks.d3d_present()",
                "assert(#queued == 7, 'unconfirmed request retried without the retry lock')",
                "confirm(172)",
                "now = now + 1.2",
                "callbacks.d3d_present()",
                "assert(#queued == 7, 'a late exact cast-start acknowledgement was ignored and retried')",
                "invoke('/oc', 'day')",
                "assert(#queued == 8, 'replacement setup did not submit its first bounded attempt')",
                "invoke('/oc', 'day')",
                "assert(#queued == 8, 'replacement discarded the in-flight acknowledgement state')",
                "confirm(172)",
                "now = now + 5",
                "callbacks.d3d_present()",
                "assert(#queued == 8, 'confirmed in-flight attempt did not cancel the replacement intent')",
                "invoke('/oc', 'day')",
                "assert(#queued == 9, 'action-lock retry setup did not submit its first attempt')",
                "now = now + 2.1",
                "callbacks.d3d_present()",
                "assert(#queued == 9, 'unconfirmed request retried without the retry lock')",
                "now = now + 1.2",
                "callbacks.d3d_present()",
                "assert(#queued == 10 and queued[10].command == '/ma \"Water IV\" <t>', 'unconfirmed action-lock rejection was not retried')",
                "confirm(172)",
                "castCount = 50",
                "invoke('/oc', 'day')",
                "assert(#queued == 10, 'second busy cast request was submitted immediately')",
                "targetIndex = 400",
                "targetName = 'Changed Rabbit'",
                "castCount = 0",
                "now = now + 4",
                "callbacks.d3d_present()",
                "assert(#queued == 10, 'target change did not cancel the pending cast request')",
                "targetIndex = 321",
                "targetName = 'Proof Rabbit'",
                "castCount = 50",
                "invoke('/oc', 'day')",
                "assert(#queued == 10, 'third busy cast request was submitted immediately')",
                "assert(callbacks.unload ~= nil, 'pending cast cleanup was not registered')",
                "callbacks.unload()",
                "castCount = 0",
                "now = now + 4",
                "callbacks.d3d_present()",
                "assert(#queued == 10, 'unload did not cancel the pending cast request')",
                "castCount = 50",
                "invoke('/oc', 'day')",
                "now = now + 0.06",
                "castCount = 49",
                "callbacks.d3d_present()",
                "now = now + 0.11",
                "callbacks.d3d_present()",
                "assert(#queued == 10, 'cast that moved and then froze bypassed the post-cast settle')",
                "now = now + 3.2",
                "callbacks.d3d_present()",
                "assert(#queued == 11 and queued[11].command == '/ma \"Water IV\" <t>', 'moving then frozen cast count never released after the full settle')",
                "confirm(172)",
                "castCount = 50",
                "invoke('/oc', 'day')",
                "assert(#queued == 11, 'frozen positive cast count submitted before the initial probe')",
                "now = now + 0.05",
                "invoke('/oc', 'day')",
                "assert(#queued == 11, 'replacement restarted by submitting during the initial probe')",
                "now = now + 0.06",
                "callbacks.d3d_present()",
                "assert(#queued == 12 and queued[12].command == '/ma \"Water IV\" <t>', 'interrupted cast left a frozen positive count classified as busy')",
                "confirm(172)",
                "activeSettings.dayTierCeiling = 3",
                "activeSettings.weaknessTierCeiling = 0",
                "castCount = 0",
                "invoke('/oc', 'day')",
                "assert(#queued == 13 and queued[13].command == '/ma \"Water III\" <t>', 'day did not apply its independent tier ceiling')",
                "confirm(171)",
                "rawTime = (80006 * 3456) - 92514960",
                "invoke('/oc', 'day')",
                "assert(#queued == 14 and queued[14].command == '/ma \"Dia III\" <t>', 'Lightsday did not use the strongest ready Dia tier')",
                "confirm(25)",
                "rawTime = (80007 * 3456) - 92514960",
                "invoke('/oc', 'day')",
                "assert(#queued == 15 and queued[15].command == '/ma \"Bio III\" <t>', 'Darksday did not use the strongest ready Bio tier')",
                "confirm(232)",
                "activeSettings.dayTierCeiling = 2",
                "invoke('/oc', 'day')",
                "assert(#queued == 16 and queued[16].command == '/ma \"Bio II\" <t>', 'Darksday Bio selection bypassed the day tier ceiling')",
                "confirm(231)",
                "castbarAvailable = false",
                "invoke('/oc', 'day')",
                "assert(#queued == 16, 'missing cast-bar state submitted a one-shot spell')",
                "print('PASS OddCast day and missing weakness data fail-closed command contract')",
            )
        ),
        encoding="utf-8",
        newline="\n",
    )

    completed = subprocess.run(
        [luajit, str(driver)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (
        "PASS OddCast day and missing weakness data fail-closed command contract"
        in completed.stdout
    )


def test_oddcast_global_mob_weakness_selection_contract(tmp_path: Path) -> None:
    luajit = shutil.which("luajit")
    assert luajit is not None
    assert ODDCAST_PATH.is_file()

    driver = tmp_path / "oddcast_weakness_contract.lua"
    driver.write_text(
        "\n".join(
            (
                "local ODDCAST_PATH = [[" + ODDCAST_PATH.as_posix() + "]]",
                "local realDofile = dofile",
                "local callbacks, queued, output, dataFiles, loadCounts = {}, {}, {}, {}, {}",
                "local targetIndex, targetServerId, targetName, targetZone = 321, 123456, 'Proof Rabbit', 100",
                "local playerServerId = 777777",
                "local known, timers, mutateTarget = {}, {}, false",
                "local activeSettings = { target='<t>', dayTierCeiling=5, weaknessTierCeiling=5, showRoutineChat=true, language='en' }",
                "local sourceSha = 'sha256:' .. string.rep('a', 64)",
                "local fileSha = 'sha256:' .. string.rep('b', 64)",
                "local elements = { 'Fire', 'Ice', 'Wind', 'Earth', 'Lightning', 'Water' }",
                "local resources = {}",
                "local function spell(id, name)",
                "    resources[id] = { Name={name}, ManaCost=1, LevelRequired={ [5]=1 } }",
                "end",
                "spell(147, 'Fire IV')",
                "spell(148, 'Fire V')",
                "spell(167, 'Thunder IV')",
                "spell(153, 'Blizzard V')",
                "spell(158, 'Aero V')",
                "spell(163, 'Stone V')",
                "spell(168, 'Thunder V')",
                "spell(173, 'Water V')",
                "T = function(value) return value end",
                "struct = { unpack=function(_, data) return data.actorId end }",
                "package.preload['common'] = function() return true end",
                "package.preload['imgui'] = function() return {} end",
                "package.preload['settings'] = function()",
                "    return { load=function() return activeSettings end, save=function() return true end, register=function() return true end }",
                "end",
                "package.loaded['ffi'] = nil",
                "package.preload['ffi'] = function() return { cdef=function() end, cast=function() error('unexpected <bt> lookup') end } end",
                "package.preload['chat'] = function()",
                "    return { header=function(v) return '['..v..'] ' end, message=function(v) return v end, error=function(v) return v end }",
                "end",
                "local originalPrint = print",
                "print = function(value) output[#output + 1] = tostring(value); originalPrint(value) end",
                "dofile = function(path)",
                "    if string.sub(path, 1, 8) == 'fixture/' then",
                "        loadCounts[path] = (loadCounts[path] or 0) + 1",
                "        local value = dataFiles[path]",
                "        if value == nil then error('missing fixture: ' .. path) end",
                "        return value",
                "    end",
                "    return realDofile(path)",
                "end",
                "ashita = {",
                "    events = { register=function(name, _, cb) callbacks[name]=cb end },",
                "    memory = { find=function() return 0 end, read_uint32=function() return 0 end },",
                "    bits = { unpack_be=function(data, base, offset, length) if base == 10 and offset == 2 and length == 4 then return data.category end if base == 0 and offset == 213 and length == 17 then return data.spellId end error('unexpected packet bit field') end },",
                "}",
                "local target = { GetIsSubTargetActive=function() return 0 end, GetTargetIndex=function() return targetIndex end }",
                "local entity = {",
                "    GetSpawnFlags=function() return 0x10 end,",
                "    GetName=function() return targetName end,",
                "    GetServerId=function() return targetServerId end,",
                "}",
                "local player = {",
                "    GetMainJob=function() return 4 end, GetMainJobLevel=function() return 99 end,",
                "    GetSubJob=function() return 1 end, GetSubJobLevel=function() return 49 end,",
                "    HasSpell=function(_, id) return known[id] end,",
                "}",
                "local party = { GetMemberMP=function() return 9999 end, GetMemberZone=function() return targetZone end, GetMemberServerId=function() return playerServerId end }",
                "local recast = { GetSpellTimer=function(_, id)",
                "    if mutateTarget then",
                "        targetServerId, targetZone, mutateTarget = 654321, 101, false",
                "    end",
                "    return timers[id] or 0",
                "end }",
                "local castbar = { GetCount=function() return 0 end }",
                "local memory = {",
                "    GetTarget=function() return target end, GetEntity=function() return entity end,",
                "    GetPlayer=function() return player end, GetParty=function() return party end,",
                "    GetRecast=function() return recast end, GetCastBar=function() return castbar end,",
                "}",
                "local resourceManager = { GetSpellById=function(_, id) return resources[id] end }",
                "local chatManager = { QueueCommand=function(_, mode, command) queued[#queued + 1]={mode=mode, command=command} end }",
                "AshitaCore = {",
                "    GetMemoryManager=function() return memory end,",
                "    GetResourceManager=function() return resourceManager end,",
                "    GetChatManager=function() return chatManager end,",
                "}",
                "local function indexData(profile)",
                "    return {",
                "        schema=2, sourceSha256=sourceSha, elements=elements, profiles={ [7]=profile },",
                "        names={ ['proof rabbit']=7 }, familyPrefixes={ ['rabbit']=7 },",
                "    }",
                "end",
                "local function reset(indexValue)",
                "    callbacks, queued, output, dataFiles, loadCounts = {}, {}, {}, {}, {}",
                "    targetIndex, targetServerId, targetName, targetZone = 321, 123456, 'Proof Rabbit', 100",
                "    known = { [147]=true, [148]=true, [153]=true, [158]=true, [163]=true, [167]=true, [168]=true, [173]=true }",
                "    timers, mutateTarget = {}, false",
                "    if indexValue ~= nil then dataFiles['fixture/weakness_data.lua'] = indexValue end",
                "    addon = { path='fixture/' }",
                "    realDofile(ODDCAST_PATH)",
                "end",
                "local function invoke(prefix, action)",
                "    local event={ command={ args=function() return {prefix, action} end }, blocked=false }",
                "    callbacks.command(event)",
                "    assert(event.blocked == true, 'OddCast command was not blocked')",
                "end",
                "local function confirm(spellId)",
                "    callbacks.packet_in({id=0x028, data={actorId=playerServerId}, data_raw={category=8,spellId=spellId}})",
                "end",
                "local dominant = { 10000, -5000, -5000, -5000, -5000, -5000, 0, 1, 1, 1, 1, 1 }",
                "reset(indexData(dominant))",
                "invoke('/oc', 'weak')",
                "assert(#queued == 1 and queued[1].command == '/ma \"Fire V\" <t>', 'exact dominant lookup did not choose Fire V')",
                "confirm(148)",
                "invoke('/oddcast', 'weakness')",
                "assert(#queued == 2 and queued[2].command == '/ma \"Fire V\" <t>', 'weakness alias did not choose Fire V')",
                "confirm(148)",
                "assert(loadCounts['fixture/weakness_data.lua'] == 1, 'weakness index was not cached')",
                "timers[148] = 1",
                "invoke('/oc', 'weak')",
                "assert(#queued == 3 and queued[3].command == '/ma \"Fire IV\" <t>', 'weakness did not use the highest ready tier per element')",
                "confirm(147)",
                "local sawClaim = false",
                "for _, line in ipairs(output) do if string.find(line, 'typical family baseline', 1, true) then sawClaim=true end end",
                "assert(sawClaim, 'success output omitted the typical family boundary')",
                "targetName = 'Custom Catseye Mob'",
                "invoke('/oc', 'weak')",
                "assert(#queued == 4 and queued[4].command == '/ma \"Thunder V\" <t>', 'unidentified target did not choose the strongest modeled ready spell')",
                "confirm(168)",
                "local sawFallback = false",
                "for _, line in ipairs(output) do if string.find(line, 'Target weakness unavailable', 1, true) then sawFallback=true end end",
                "assert(sawFallback, 'unidentified-target fallback was not explained')",
                "reset(indexData(dominant))",
                "targetZone = 199",
                "invoke('/oc', 'weak')",
                "assert(#queued == 1 and queued[1].command == '/ma \"Fire V\" <t>', 'zone changed the mob-family weakness lookup')",
                "confirm(148)",
                "local malformed = indexData(dominant); malformed.schema = 1",
                "reset(malformed)",
                "invoke('/oc', 'weak')",
                "assert(#queued == 0, 'malformed index queued a spell')",
                "local missingField = { 10000, -5000, -5000, -5000, -5000, -5000, 0, 1, 1, 1, 1 }",
                "reset(indexData(missingField))",
                "invoke('/oc', 'weak')",
                "assert(#queued == 0, 'profile with a missing field queued a spell')",
                "local outOfRangeRank = { 0, 0, 0, 0, 0, 0, -4, -3, 0, 0, 0, 0 }",
                "reset(indexData(outOfRangeRank))",
                "known = { [148]=true, [153]=true }",
                "invoke('/oc', 'weak')",
                "assert(#queued == 0, 'out-of-range resistance rank was compared instead of rejected')",
                "local tied = { 625, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 }",
                "reset(indexData(tied))",
                "known = { [148]=true, [153]=true }",
                "invoke('/oc', 'weak')",
                "assert(#queued == 1 and queued[1].command == '/ma \"Blizzard V\" <t>', 'equal baseline/rank tie was not broken by spell power')",
                "confirm(153)",
                "local tradeoff = { 10000, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0 }",
                "reset(indexData(tradeoff))",
                "known = { [148]=true, [153]=true }",
                "invoke('/oc', 'weak')",
                "assert(#queued == 1 and queued[1].command == '/ma \"Blizzard V\" <t>', 'best resistance rank did not win the potency tradeoff')",
                "confirm(153)",
                "reset(indexData(dominant))",
                "mutateTarget = true",
                "invoke('/oc', 'weak')",
                "assert(#queued == 0, 'target identity mutation queued a spell')",
                "reset(nil)",
                "invoke('/oc', 'weak')",
                "assert(#queued == 0, 'missing weakness data queued a spell')",
                "dataFiles['fixture/weakness_data.lua'] = indexData(dominant)",
                "invoke('/oc', 'weak')",
                "assert(#queued == 1 and queued[1].command == '/ma \"Fire V\" <t>', 'a failed data load was cached instead of retried')",
                "confirm(148)",
                "reset(indexData(dominant))",
                "activeSettings.dayTierCeiling = 0",
                "activeSettings.weaknessTierCeiling = 4",
                "invoke('/oc', 'weak')",
                "assert(#queued == 1 and queued[1].command == '/ma \"Fire IV\" <t>', 'recognized weakness ignored the weakness tier ceiling')",
                "confirm(147)",
                "targetName = 'Custom Catseye Mob'",
                "invoke('/oc', 'weak')",
                "assert(#queued == 2 and queued[2].command == '/ma \"Thunder IV\" <t>', 'unknown-target fallback bypassed the weakness tier ceiling')",
                "confirm(167)",
                "print('PASS OddCast global mob weakness and dominance contract')",
            )
        ),
        encoding="utf-8",
        newline="\n",
    )

    completed = subprocess.run(
        [luajit, str(driver)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS OddCast global mob weakness and dominance contract" in completed.stdout


def test_oddcast_generated_damselfly_and_goblin_profiles_ignore_zone_identity(
    tmp_path: Path,
) -> None:
    luajit = shutil.which("luajit")
    assert luajit is not None
    assert (ODDCAST_DIR / "weakness_data.lua").is_file()

    driver = tmp_path / "oddcast_real_data_contract.lua"
    driver.write_text(
        "\n".join(
            (
                "local ODDCAST_PATH = [[" + ODDCAST_PATH.as_posix() + "]]",
                "local callbacks, queued = {}, {}",
                "local playerServerId = 777777",
                "T = function(value) return value end",
                "struct = {unpack=function(_,data) return data.actorId end}",
                "package.preload['common'] = function() return true end",
                "package.preload['imgui'] = function() return {} end",
                "package.preload['settings'] = function() local value={target='<t>',dayTierCeiling=5,weaknessTierCeiling=5,showRoutineChat=false,language='en'}; return {load=function() return value end,save=function() return true end,register=function() return true end} end",
                "package.loaded['ffi'] = nil",
                "package.preload['ffi'] = function() return {cdef=function() end,cast=function() error('unexpected <bt> lookup') end} end",
                "package.preload['chat'] = function() return { header=function(v) return '['..v..'] ' end, message=function(v) return v end, error=function(v) return v end } end",
                "addon = { path=[[" + ODDCAST_DIR.as_posix() + "/]] }",
                "ashita = { events={register=function(name, _, cb) callbacks[name]=cb end}, memory={find=function() return 0 end, read_uint32=function() return 0 end}, bits={unpack_be=function(data,base,offset,length) if base==10 and offset==2 and length==4 then return data.category end if base==0 and offset==213 and length==17 then return data.spellId end error('unexpected packet bit field') end} }",
                "local resources = {}",
                "-- Deliberately synthetic identities prove weakness is keyed by the global mob name, not a zone spawn row.",
                "local liveName, liveServerId, liveZone = 'Damselfly', 17227777, 119",
                "for _, row in ipairs({{148,'Fire V'},{153,'Blizzard V'},{158,'Aero V'},{163,'Stone V'},{168,'Thunder V'},{173,'Water V'}}) do resources[row[1]]={Name={row[2]},ManaCost=1,LevelRequired={[5]=1}} end",
                "local target={GetIsSubTargetActive=function() return 0 end,GetTargetIndex=function() return 1 end}",
                "local entity={GetSpawnFlags=function() return 0x10 end,GetName=function() return liveName end,GetServerId=function() return liveServerId end}",
                "local player={GetMainJob=function() return 4 end,GetMainJobLevel=function() return 99 end,GetSubJob=function() return 1 end,GetSubJobLevel=function() return 49 end,HasSpell=function(_, id) return resources[id] ~= nil end}",
                "local party={GetMemberMP=function() return 9999 end,GetMemberZone=function() return liveZone end,GetMemberServerId=function() return playerServerId end}",
                "local recast={GetSpellTimer=function() return 0 end}",
                "local castbar={GetCount=function() return 0 end}",
                "local memory={GetTarget=function() return target end,GetEntity=function() return entity end,GetPlayer=function() return player end,GetParty=function() return party end,GetRecast=function() return recast end,GetCastBar=function() return castbar end}",
                "local resourceManager={GetSpellById=function(_, id) return resources[id] end}",
                "local chatManager={QueueCommand=function(_, mode, command) queued[#queued+1]={mode=mode,command=command} end}",
                "AshitaCore={GetMemoryManager=function() return memory end,GetResourceManager=function() return resourceManager end,GetChatManager=function() return chatManager end}",
                "dofile(ODDCAST_PATH)",
                "local event={command={args=function() return {'/oc','weak'} end},blocked=false}",
                "callbacks.command(event)",
                "assert(event.blocked == true, 'real-data command was not consumed')",
                "assert(#queued == 1, 'Meriphataud Damselfly did not produce exactly one queue')",
                "assert(queued[1].mode == 1 and queued[1].command == '/ma \"Blizzard V\" <t>', 'Damselfly did not use the global Fly weakness profile')",
                "callbacks.packet_in({id=0x028,data={actorId=playerServerId},data_raw={category=8,spellId=153}})",
                "liveName, liveServerId, liveZone = 'Goblin Ambusher', 999999, 1",
                "callbacks.command({command={args=function() return {'/oc','weak'} end},blocked=false})",
                "assert(#queued == 2 and queued[2].command == '/ma \"Thunder V\" <t>', 'Goblin did not use the global Goblin weakness profile')",
                "callbacks.packet_in({id=0x028,data={actorId=playerServerId},data_raw={category=8,spellId=168}})",
                "print('PASS OddCast Damselfly and Goblin global family weaknesses')",
            )
        ),
        encoding="utf-8",
        newline="\n",
    )
    completed = subprocess.run(
        [luajit, str(driver)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS OddCast Damselfly and Goblin global family weaknesses" in completed.stdout


def test_oddcast_target_settings_bind_selection_and_queued_token(
    tmp_path: Path,
) -> None:
    luajit = shutil.which("luajit")
    assert luajit is not None
    addon_text = ODDCAST_PATH.read_text(encoding="utf-8")
    assert "local imgui = require('imgui');" in addon_text
    assert "target = '<t>'" in addon_text

    driver = tmp_path / "oddcast_target_settings_contract.lua"
    driver.write_text(
        "\n".join(
            (
                "local ODDCAST_PATH = [[" + ODDCAST_PATH.as_posix() + "]]",
                "local realDofile = dofile",
                "local callbacks, queued, output = {}, {}, {}",
                "local playerServerId = 777777",
                "local activeSettings, settingsCallback = {target='<t>',dayTierCeiling=5,weaknessTierCeiling=5,showRoutineChat=true,language='en'}, nil",
                "local saveCount, saveAllowed = 0, true",
                "local mainIndex, mainServerId, mainName = 321, 111111, 'Main Rabbit'",
                "local btIndex, btServerId, btName = 322, 222222, 'Battle Rabbit'",
                "local resolvedIndex, resolvedServerId, resolvedName = 323, 333333, 'Remote Rabbit'",
                "local nonMonsterIndex, nonMonsterServerId = 324, 444444",
                "local btPresent, btSignatureAddress = true, 0",
                "local subTargetActive, mutateBattleOnTimer, mutateResolvedOnTimer = 0, false, false",
                "local zone = 100",
                "local now, castCount = 0, 0",
                "local rawTime = (80002 * 3456) - 92514960",
                "local sourceSha = 'sha256:' .. string.rep('a', 64)",
                "local elements = {'Fire','Ice','Wind','Earth','Lightning','Water'}",
                "local fireDominant = {10000,-5000,-5000,-5000,-5000,-5000,0,1,1,1,1,1}",
                "local iceDominant = {-5000,10000,-5000,-5000,-5000,-5000,1,0,1,1,1,1}",
                "local dataFiles = {",
                "  ['fixture/weakness_data.lua']={schema=2,sourceSha256=sourceSha,elements=elements,profiles={[7]=fireDominant,[8]=iceDominant},names={['main rabbit']=7,['battle rabbit']=8,['remote rabbit']=7},familyPrefixes={['rabbit']=7}},",
                "}",
                "local resources = {}",
                "for _, row in ipairs({{148,'Fire V'},{153,'Blizzard V'},{158,'Aero V'},{163,'Stone V'},{168,'Thunder V'},{173,'Water V'}}) do",
                "  resources[row[1]]={Name={row[2]},ManaCost=1,LevelRequired={[5]=1}}",
                "end",
                "local originalPrint = print",
                "print=function(value) output[#output+1]=tostring(value); originalPrint(value) end",
                "os.clock=function() return now end",
                "T=function(value) return value end",
                "struct={unpack=function(_,data) return data.actorId end}",
                "package.preload['common']=function() return true end",
                "package.preload['chat']=function() return {header=function(v) return '['..v..'] ' end,message=function(v) return v end,error=function(v) return v end} end",
                "package.preload['imgui']=function() return {} end",
                "package.preload['settings']=function() return {",
                "  load=function() return activeSettings end,",
                "  save=function() saveCount=saveCount+1; return saveAllowed end,",
                "  reload=function() if settingsCallback then settingsCallback(activeSettings) end return true end,",
                "  register=function(_,_,callback) settingsCallback=callback; return true end,",
                "} end",
                "package.loaded['ffi']=nil",
                "package.preload['ffi']=function() return {",
                "  cdef=function() end,",
                "  cast=function(_, address)",
                "    assert(address==btSignatureAddress, 'unexpected battle target address')",
                "    return function() if not btPresent then return nil end return {id={GuideNo=btIndex,UniqueNo=btServerId}} end",
                "  end,",
                "} end",
                "dofile=function(path) if dataFiles[path] ~= nil then return dataFiles[path] end return realDofile(path) end",
                "ashita={events={register=function(name,_,callback) callbacks[name]=callback end},memory={",
                "  find=function(_,_,signature) if string.sub(signature,1,4)=='66A1' then return btSignatureAddress end return 1000 end,",
                "  read_uint32=function(address) if address==1052 then return 2000 end if address==2012 then return rawTime end return 0 end,",
                "},bits={unpack_be=function(data,base,offset,length) if base==10 and offset==2 and length==4 then return data.category end if base==0 and offset==213 and length==17 then return data.spellId end error('unexpected packet bit field') end}}",
                "local selectedIndex, selectedServerId = mainIndex, mainServerId",
                "local target={GetIsSubTargetActive=function() return subTargetActive end,GetTargetIndex=function(_,slot) if slot==1 then return btIndex end return selectedIndex end,GetServerId=function(_,slot) if slot==1 then return btServerId end return selectedServerId end,SetTarget=function(_,index,force) assert(force==true,'resolved target selection was not forced') selectedIndex=index if index==mainIndex then selectedServerId=mainServerId elseif index==btIndex then selectedServerId=btServerId elseif index==resolvedIndex then selectedServerId=resolvedServerId else selectedServerId=0 end end}",
                "local entity={",
                "  GetEntityMapSize=function() return 1024 end,",
                "  GetSpawnFlags=function(_,index) if index==mainIndex or index==btIndex or index==resolvedIndex then return 0x10 end return 0 end,",
                "  GetName=function(_,index) if index==mainIndex then return mainName end if index==btIndex then return btName end if index==resolvedIndex then return resolvedName end return '' end,",
                "  GetServerId=function(_,index) if index==mainIndex then return mainServerId end if index==btIndex then return btServerId end if index==resolvedIndex then return resolvedServerId end return 0 end,",
                "}",
                "local player={GetMainJob=function() return 4 end,GetMainJobLevel=function() return 99 end,GetSubJob=function() return 1 end,GetSubJobLevel=function() return 49 end,HasSpell=function(_,id) return resources[id] ~= nil end}",
                "local party={GetMemberMP=function() return 9999 end,GetMemberZone=function() return zone end,GetMemberServerId=function() return playerServerId end}",
                "local recast={GetSpellTimer=function() if mutateBattleOnTimer then btIndex,btServerId,btName,mutateBattleOnTimer=323,333333,'Changed Rabbit',false elseif mutateResolvedOnTimer then resolvedName,mutateResolvedOnTimer='Changed Remote Rabbit',false end return 0 end}",
                "local castbar={GetCount=function() return castCount end}",
                "local memory={GetTarget=function() return target end,GetEntity=function() return entity end,GetPlayer=function() return player end,GetParty=function() return party end,GetRecast=function() return recast end,GetCastBar=function() return castbar end}",
                "local resourceManager={GetSpellById=function(_,id) return resources[id] end,GetEntityIndexById=function() error('live-unsupported ID lookup must not be used') end}",
                "local chatManager={QueueCommand=function(_,mode,command) queued[#queued+1]={mode=mode,command=command} end}",
                "AshitaCore={GetMemoryManager=function() return memory end,GetResourceManager=function() return resourceManager end,GetChatManager=function() return chatManager end}",
                "addon={path='fixture/'}",
                "realDofile(ODDCAST_PATH)",
                "local function invoke(...) local values={...}; local event={command={args=function() return values end},blocked=false}; callbacks.command(event); assert(event.blocked==true,'OddCast command was not blocked') end",
                "local function outputHas(needle) for _, line in ipairs(output) do if string.find(line,needle,1,true) then return true end end return false end",
                "invoke('/oc','settings')",
                "assert(outputHas('Target token: <t>'),'settings did not show default <t>')",
                "assert(outputHas('Day tier ceiling: V (5)'),'settings did not show the default day ceiling')",
                "assert(outputHas('Weakness tier ceiling: V (5)'),'settings did not show the default weakness ceiling')",
                "assert(outputHas('Routine chat messages: On'),'settings did not show the routine chat setting')",
                "assert(outputHas('Language: English'),'settings did not show the default language')",
                "invoke('/oc','language','fr')",
                "assert(activeSettings.language=='fr' and outputHas('Langue mise à jour : Français'),'French language command was not persisted or localized')",
                "invoke('/oc','target')",
                "assert(string.find(output[#output],'Jeton de cible : <t>',1,true),'French target query was not localized')",
                "invoke('/oc','lang','en')",
                "assert(activeSettings.language=='en','language alias could not restore English')",
                "saveCount=0",
                "local tierInputs={{'1',1},{'I',1},{'2',2},{'II',2},{'3',3},{'III',3},{'4',4},{'iv',4},{'5',5},{'V',5}}",
                "for _, pair in ipairs(tierInputs) do",
                "  local previousWeakness=activeSettings.weaknessTierCeiling",
                "  invoke('/oc','tier','day',pair[1])",
                "  assert(activeSettings.dayTierCeiling==pair[2] and activeSettings.weaknessTierCeiling==previousWeakness,'day tier input was not parsed or changed weakness')",
                "end",
                "for _, pair in ipairs(tierInputs) do",
                "  local previousDay=activeSettings.dayTierCeiling",
                "  invoke('/oc','tier','weak',pair[1])",
                "  assert(activeSettings.weaknessTierCeiling==pair[2] and activeSettings.dayTierCeiling==previousDay,'weakness tier input was not parsed or changed day')",
                "end",
                "assert(saveCount==20,'valid Arabic and Roman tier inputs were not persisted independently')",
                "invoke('/oc','tier','day','III')",
                "invoke('/oc','tier','day','clear')",
                "assert(activeSettings.dayTierCeiling==5 and activeSettings.weaknessTierCeiling==5,'clear did not restore only the selected ceiling to V')",
                "local tierSaveCount=saveCount",
                "invoke('/oc','tier','day','0')",
                "invoke('/oc','tier','weak','VI')",
                "invoke('/oc','tier','day','III','extra')",
                "assert(saveCount==tierSaveCount and activeSettings.dayTierCeiling==5 and activeSettings.weaknessTierCeiling==5,'invalid tier input changed or saved settings')",
                "invoke('/oc','tier')",
                "invoke('/oc','tier','day')",
                "invoke('/oc','tier','weakness')",
                "assert(saveCount==tierSaveCount,'tier queries unexpectedly saved settings')",
                "saveAllowed=false",
                "invoke('/oc','tier','weak','II')",
                "assert(activeSettings.weaknessTierCeiling==5 and activeSettings.dayTierCeiling==5 and saveCount==tierSaveCount+1,'failed tier save did not roll back only its field')",
                "saveAllowed=true",
                "saveCount=0",
                "invoke('/oc','target')",
                "assert(string.find(output[#output],'Target token: <t>',1,true),'target query did not show default <t>')",
                "invoke('/oc','target','<stnpc>')",
                "assert(activeSettings.target=='<t>' and saveCount==0 and #queued==0,'unsafe target token changed settings')",
                "invoke('/oc','target','<bt>','extra')",
                "assert(activeSettings.target=='<t>' and saveCount==0,'target command accepted extra arguments')",
                "invoke('/oddcast','target','<BT>')",
                "assert(activeSettings.target=='<bt>' and saveCount==1,'<bt> was not normalized and saved')",
                "invoke('/oc','weak')",
                "assert(#queued==0,'missing <bt> signature queued a spell')",
                "btSignatureAddress=4242",
                "invoke('/oc','weak')",
                "assert(#queued==1 and queued[1].mode==1 and queued[1].command=='/ma \"Blizzard V\" <bt>','<bt> did not bind the battle target and queue token')",
                "callbacks.packet_in({id=0x028,data={actorId=playerServerId},data_raw={category=8,spellId=153}})",
                "invoke('/oc','day')",
                "assert(#queued==2 and queued[2].command=='/ma \"Water V\" <bt>','day did not use the configured <bt> resolver and queue token')",
                "callbacks.packet_in({id=0x028,data={actorId=playerServerId},data_raw={category=8,spellId=173}})",
                "mutateBattleOnTimer=true",
                "invoke('/oc','weak')",
                "assert(#queued==2,'changed battle target queued a spell')",
                "btIndex,btServerId,btName=322,222222,'Battle Rabbit'",
                "btPresent=false",
                "invoke('/oc','weak')",
                "assert(#queued==2,'absent battle target queued a spell')",
                "btPresent=true",
                "invoke('/oc','target','<t>')",
                "assert(activeSettings.target=='<t>' and saveCount==2,'<t> was not saved')",
                "subTargetActive=1",
                "invoke('/oc','weak')",
                "assert(#queued==2,'active subtarget allowed a <t> spell queue')",
                "subTargetActive=0",
                "invoke('/oc','weak')",
                "assert(#queued==3 and queued[3].command=='/ma \"Fire V\" <t>','<t> did not bind the main target and queue token')",
                "callbacks.packet_in({id=0x028,data={actorId=playerServerId},data_raw={category=8,spellId=148}})",
                "invoke('/oc','weak',tostring(resolvedServerId))",
                "assert(#queued==4 and queued[4].command=='/ma \"Fire V\" <t>' and selectedIndex==resolvedIndex and selectedServerId==resolvedServerId,'Multisend-resolved server ID did not select the exact remote target and cast through <t>')",
                "callbacks.packet_in({id=0x028,data={actorId=playerServerId},data_raw={category=8,spellId=148}})",
                "invoke('/oc','day',tostring(resolvedServerId))",
                "assert(#queued==5 and queued[5].command=='/ma \"Water V\" <t>','day did not select the MultiSend-resolved server ID and cast through <t>')",
                "callbacks.packet_in({id=0x028,data={actorId=playerServerId},data_raw={category=8,spellId=173}})",
                "mutateResolvedOnTimer=true",
                "invoke('/oc','weak',tostring(resolvedServerId))",
                "assert(#queued==5,'resolved target identity mutation queued a spell')",
                "resolvedName='Remote Rabbit'",
                "target:SetTarget(mainIndex,true)",
                "invoke('/oc','weak','[T]')",
                "assert(#queued==6 and queued[6].command=='/ma \"Fire V\" <t>' and selectedIndex==mainIndex,'direct weak [t] did not capture and select the local main target')",
                "callbacks.packet_in({id=0x028,data={actorId=playerServerId},data_raw={category=8,spellId=148}})",
                "subTargetActive=1",
                "invoke('/oc','day','[t]')",
                "assert(#queued==7 and queued[7].command=='/ma \"Water V\" <t>' and selectedIndex==btIndex,'direct day [t] did not capture and select the active subtarget')",
                "callbacks.packet_in({id=0x028,data={actorId=playerServerId},data_raw={category=8,spellId=173}})",
                "subTargetActive=0",
                "invoke('/oc','weak','0')",
                "invoke('/oc','weak','4294967296')",
                "invoke('/oc','weak','1.5')",
                "invoke('/oc','weak','[me]')",
                "invoke('/oc','weak','555555')",
                "invoke('/oc','weak',tostring(nonMonsterServerId))",
                "invoke('/oc','weak',tostring(resolvedServerId),'extra')",
                "assert(#queued==7 and activeSettings.target=='<t>' and saveCount==2,'invalid one-shot targets changed persistent settings or queued a spell')",
                "settingsCallback({target='<stnpc>',dayTierCeiling=5,weaknessTierCeiling=5,showRoutineChat=true,language='en'})",
                "invoke('/oc','weak')",
                "assert(#queued==7,'corrupt persisted target token queued a spell')",
                "invoke('/oc','weak',tostring(resolvedServerId))",
                "assert(#queued==8 and queued[8].command=='/ma \"Fire V\" <t>' and selectedIndex==resolvedIndex,'a corrupt default target blocked an explicit MultiSend-resolved target')",
                "callbacks.packet_in({id=0x028,data={actorId=playerServerId},data_raw={category=8,spellId=148}})",
                "castCount=50",
                "invoke('/oc','weak',tostring(resolvedServerId))",
                "assert(#queued==8,'busy explicit-ID request submitted before the cast check completed')",
                "settingsCallback({target='<bt>',dayTierCeiling=5,weaknessTierCeiling=5,showRoutineChat=true,language='en'})",
                "now=now+0.11",
                "callbacks.d3d_present()",
                "assert(#queued==9 and queued[9].command=='/ma \"Fire V\" <t>' and selectedIndex==resolvedIndex,'target-setting change canceled or retargeted the pending explicit-ID request')",
                "now=now+2.1",
                "callbacks.d3d_present()",
                "assert(#queued==9,'explicit-ID request retried before the bounded retry lock')",
                "now=now+1.2",
                "callbacks.d3d_present()",
                "assert(#queued==10 and queued[10].command=='/ma \"Fire V\" <t>' and selectedIndex==resolvedIndex,'retry did not reselect the explicit target server ID')",
                "callbacks.packet_in({id=0x028,data={actorId=playerServerId},data_raw={category=8,spellId=148}})",
                "castCount=0",
                "settingsCallback({target='<stnpc>',dayTierCeiling=5,weaknessTierCeiling=5,showRoutineChat=true,language='en'})",
                "invoke('/oc','settings')",
                "assert(outputHas('target setting is invalid'),'invalid persisted setting was not explained')",
                "callbacks.d3d_present()",
                "invoke('/oc','target','<t>')",
                "assert(saveCount==3,'valid command did not repair an invalid persisted setting')",
                "saveAllowed=false",
                "invoke('/oc','target','<bt>')",
                "assert(activeSettings.target=='<t>' and saveCount==4,'failed settings save did not roll back')",
                "saveAllowed=true",
                "invoke('/oc','chat','off')",
                "assert(activeSettings.showRoutineChat==false and saveCount==5,'chat off was not persisted')",
                "local quietOutputCount=#output",
                "invoke('/oc','weak')",
                "assert(#queued==11,'chat off changed casting behavior')",
                "now=now+2.1",
                "callbacks.d3d_present()",
                "assert(#queued==11,'quiet request retried before the bounded retry lock')",
                "now=now+1.2",
                "callbacks.d3d_present()",
                "assert(#queued==12,'quiet request did not retry normally')",
                "callbacks.packet_in({id=0x028,data={actorId=playerServerId},data_raw={category=8,spellId=148}})",
                "assert(#output==quietOutputCount,'routine submission, retry, or confirmation text was printed while chat was off')",
                "invoke('/oc','weak','[me]')",
                "assert(#output>quietOutputCount and outputHas('Unsupported one-shot target'),'chat off hid an actionable error')",
                "invoke('/oc','chat')",
                "assert(outputHas('Routine chat messages: Off'),'chat query was hidden while routine chat was off')",
                "print('PASS OddCast target settings and exact token binding')",
            )
        ),
        encoding="utf-8",
        newline="\n",
    )
    completed = subprocess.run(
        [luajit, str(driver)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (
        "PASS OddCast target settings and exact token binding"
        in completed.stdout
    )


def test_oddcast_native_settings_gui_is_safe_and_verifies_persistence(
    tmp_path: Path,
) -> None:
    luajit = shutil.which("luajit")
    assert luajit is not None

    driver = tmp_path / "oddcast_gui_contract.lua"
    driver.write_text(
        r"""
local ODDCAST_PATH = [[__ODDCAST_PATH__]]
local callbacks, output, queued = {}, {}, {}
local settingsCallback = nil
local activeSettings = { target='<t>', onboardingComplete=true }
local persisted = { target='<t>', onboardingComplete=true }
local saveCount, reloadCount = 0, 0
local saveResult, reloadResult, writeThrough = true, true, true

local function copySettings(value)
    return {
        target=value.target,
        dayTierCeiling=value.dayTierCeiling,
        weaknessTierCeiling=value.weaknessTierCeiling,
        showRoutineChat=value.showRoutineChat,
        language=value.language,
        onboardingComplete=value.onboardingComplete,
    }
end

local originalPrint = print
print = function(value) output[#output + 1] = tostring(value); originalPrint(value) end
T = function(value) return value end
struct = { unpack=function() return 0 end }
addon = { path='fixture/' }
ImGuiCond_FirstUseEver = 4
ImGuiWindowFlags_NoCollapse = 32
ImGuiWindowFlags_AlwaysVerticalScrollbar = 16384
package.path = ODDCAST_PATH:match('^(.*[/\\])') .. '?.lua;' .. package.path

local ui = {
    calls=0,
    beginDepth=0,
    comboDepth=0,
    click=nil,
    openCombo=nil,
    closeOnBegin=false,
    failNextBegin=false,
    failNextText=false,
}
local function uiCall() ui.calls = ui.calls + 1 end
local function assertString(value, name)
    assert(type(value) == 'string' and value ~= '', name .. ' must be a non-empty string')
end

local imgui = {}
imgui.SetNextWindowSize = function(size, condition)
    uiCall()
    assert(type(size) == 'table' and type(size[1]) == 'number' and type(size[2]) == 'number', 'window size must be a numeric vector')
    assert(type(condition) == 'number', 'window condition must be numeric')
end
imgui.Begin = function(title, open, flags)
    uiCall()
    assertString(title, 'window title')
    assert(type(open) == 'table' and type(open[1]) == 'boolean', 'window open state must be a boolean ref')
    assert(type(flags) == 'number', 'window flags must be numeric')
    assert(flags == ImGuiWindowFlags_AlwaysVerticalScrollbar, 'window must keep the stable scrollbar without disabling native collapse')
    assert(ui.beginDepth == 0, 'nested Begin call')
    if ui.failNextBegin then ui.failNextBegin = false; error('synthetic Begin failure') end
    ui.beginDepth = 1
    if ui.closeOnBegin then
        ui.closeOnBegin = false
        open[1] = false
    end
    return true
end
imgui.End = function()
    uiCall()
    assert(ui.beginDepth == 1, 'End without Begin')
    ui.beginDepth = 0
end
imgui.Text = function(value)
    uiCall()
    assertString(value, 'text')
    if ui.failNextText then ui.failNextText = false; error('synthetic render failure') end
end
imgui.TextWrapped = function(value) uiCall(); assertString(value, 'wrapped text') end
imgui.Separator = function() uiCall() end
imgui.Spacing = function() uiCall() end
imgui.SameLine = function() uiCall() end
imgui.RadioButton = function(label, selected)
    uiCall()
    assertString(label, 'radio label')
    assert(type(selected) == 'boolean', 'radio selected state must be boolean')
    if ui.click == label then ui.click = nil; return true end
    return false
end
imgui.Checkbox = function(label, value)
    uiCall()
    assertString(label, 'checkbox label')
    assert(type(value) == 'table' and type(value[1]) == 'boolean', 'checkbox state must be a boolean ref')
    if ui.click == label then value[1] = not value[1]; ui.click = nil; return true end
    return false
end
imgui.BeginCombo = function(label, preview)
    uiCall()
    assertString(label, 'combo label')
    assertString(preview, 'combo preview')
    local opened = ui.openCombo == label
    if opened then
        assert(ui.comboDepth == 0, 'nested combo')
        ui.comboDepth = 1
    end
    return opened
end
imgui.Selectable = function(label, selected)
    uiCall()
    assertString(label, 'selectable label')
    assert(type(selected) == 'boolean', 'selectable selected state must be boolean')
    if ui.click == label then ui.click = nil; return true end
    return false
end
imgui.EndCombo = function()
    uiCall()
    assert(ui.comboDepth == 1, 'EndCombo without BeginCombo')
    ui.comboDepth = 0
end
imgui.Button = function(label)
    uiCall()
    assertString(label, 'button label')
    if ui.click == label then ui.click = nil; return true end
    return false
end

package.preload['common'] = function() return true end
package.preload['imgui'] = function() return imgui end
package.preload['chat'] = function()
    return { header=function(v) return '['..v..'] ' end, message=function(v) return v end, error=function(v) return v end }
end
package.loaded['ffi'] = nil
package.preload['ffi'] = function() return { cdef=function() end, cast=function() error('unexpected cast') end } end
package.preload['settings'] = function()
    return {
        load=function(defaults)
            for key, value in pairs(defaults) do
                if activeSettings[key] == nil then activeSettings[key] = value end
            end
            persisted = copySettings(activeSettings)
            return activeSettings
        end,
        save=function()
            saveCount = saveCount + 1
            if saveResult == 'error' then error('synthetic save failure') end
            if saveResult ~= true then return false end
            if writeThrough then persisted = copySettings(activeSettings) end
            return true
        end,
        reload=function()
            reloadCount = reloadCount + 1
            if reloadResult ~= true then return false end
            activeSettings = copySettings(persisted)
            settingsCallback(activeSettings)
            return true
        end,
        register=function(_, _, callback) settingsCallback = callback; return true end,
    }
end

ashita = {
    events={ register=function(name, _, callback) callbacks[name] = callback end },
    memory={ find=function() return 0 end, read_uint32=function() return 0 end },
    bits={ unpack_be=function() return 0 end },
}

dofile(ODDCAST_PATH)
assert(activeSettings.dayTierCeiling == 5 and activeSettings.weaknessTierCeiling == 5 and activeSettings.showRoutineChat == false and activeSettings.language == 'en' and activeSettings.onboardingComplete == true, 'legacy settings did not gain GUI defaults')
assert(callbacks.command ~= nil and callbacks.d3d_present ~= nil, 'GUI callbacks were not registered')

local function invoke(...)
    local values = {...}
    local event = { command={args=function() return values end}, blocked=false }
    callbacks.command(event)
    assert(event.blocked == true, 'OddCast command was not consumed')
end
local function outputHas(needle)
    for _, line in ipairs(output) do if string.find(line, needle, 1, true) then return true end end
    return false
end

callbacks.d3d_present()
assert(ui.calls == 0, 'closed GUI made ImGui calls')
invoke('/oc', 'settings')
callbacks.d3d_present()
assert(ui.beginDepth == 0 and ui.comboDepth == 0, 'initial GUI stacks were not balanced')
assert(saveCount == 0 and reloadCount == 0, 'opening settings wrote configuration')

ui.click = 'Show routine chat messages'
callbacks.d3d_present()
assert(activeSettings.showRoutineChat == true, 'routine chat checkbox did not update its setting')
assert(saveCount == 1 and reloadCount == 1, 'routine chat checkbox was not saved and read back exactly once')

ui.click = '<bt> - current battle target'
callbacks.d3d_present()
assert(activeSettings.target == '<bt>' and activeSettings.dayTierCeiling == 5 and activeSettings.weaknessTierCeiling == 5, 'target radio changed the wrong setting')
assert(saveCount == 2 and reloadCount == 2, 'target radio was not saved and read back exactly once')
ui.click = '<bt> - current battle target'
callbacks.d3d_present()
assert(saveCount == 2 and reloadCount == 2, 'selecting the active target caused a needless write')

ui.openCombo, ui.click = 'Day', 'III (3)##oddcast_day_3'
callbacks.d3d_present()
ui.openCombo = nil
assert(activeSettings.dayTierCeiling == 3 and activeSettings.weaknessTierCeiling == 5, 'day combo changed the wrong ceiling')
assert(saveCount == 3 and reloadCount == 3, 'day combo was not saved and read back exactly once')

ui.openCombo, ui.click = 'Weakness', 'II (2)##oddcast_weak_2'
callbacks.d3d_present()
ui.openCombo = nil
assert(activeSettings.dayTierCeiling == 3 and activeSettings.weaknessTierCeiling == 2, 'weakness combo changed the wrong ceiling')
assert(saveCount == 4 and reloadCount == 4, 'weakness combo was not saved and read back exactly once')

ui.openCombo, ui.click = 'Language', 'Français##oddcast_language_fr'
callbacks.d3d_present()
ui.openCombo = nil
assert(activeSettings.language == 'fr', 'language combo did not persist French')
assert(saveCount == 5 and reloadCount == 5, 'French selection was not saved and read back exactly once')
ui.openCombo, ui.click = 'Langue', 'English##oddcast_language_en'
callbacks.d3d_present()
ui.openCombo = nil
assert(activeSettings.language == 'en', 'localized language combo could not restore English')
assert(saveCount == 6 and reloadCount == 6, 'English selection was not saved and read back exactly once')

ui.click = 'Reset defaults'
callbacks.d3d_present()
assert(activeSettings.target == '<t>' and activeSettings.dayTierCeiling == 5 and activeSettings.weaknessTierCeiling == 5 and activeSettings.showRoutineChat == false and activeSettings.language == 'en', 'reset defaults was incomplete')
assert(saveCount == 7 and reloadCount == 7, 'reset defaults was not one verified write')

saveResult = false
ui.click = '<bt> - current battle target'
callbacks.d3d_present()
assert(activeSettings.target == '<t>' and saveCount == 8 and reloadCount == 7, 'failed save did not roll back without reload')
saveResult = true

writeThrough = false
ui.openCombo, ui.click = 'Day', 'III (3)##oddcast_day_3'
callbacks.d3d_present()
ui.openCombo, writeThrough = nil, true
assert(activeSettings.dayTierCeiling == 5 and saveCount == 9 and reloadCount == 8, 'read-back mismatch did not restore persisted state')
assert(outputHas('could not save and verify'), 'persistence failure was not explained')

activeSettings = { target='<invalid>', dayTierCeiling=0, weaknessTierCeiling='bad', showRoutineChat='bad', language='bad' }
settingsCallback(activeSettings)
callbacks.d3d_present()
assert(ui.beginDepth == 0 and ui.comboDepth == 0, 'corrupt settings broke GUI rendering')
ui.click = '<t> - current target'
callbacks.d3d_present()
ui.openCombo, ui.click = 'Day', 'IV (4)##oddcast_day_4'
callbacks.d3d_present()
ui.openCombo = nil
ui.openCombo, ui.click = 'Weakness', 'I (1)##oddcast_weak_1'
callbacks.d3d_present()
ui.openCombo = nil
ui.click = 'Show routine chat messages'
callbacks.d3d_present()
ui.openCombo, ui.click = 'Language', 'Español##oddcast_language_es'
callbacks.d3d_present()
ui.openCombo = nil
assert(activeSettings.target == '<t>' and activeSettings.dayTierCeiling == 4 and activeSettings.weaknessTierCeiling == 1 and activeSettings.showRoutineChat == true and activeSettings.language == 'es', 'GUI could not repair corrupt settings')
invoke('/oc', 'language', 'en')
assert(activeSettings.language == 'en', 'language command could not restore English after GUI repair')

ui.closeOnBegin = true
callbacks.d3d_present()
local closedCallCount = ui.calls
callbacks.d3d_present()
assert(ui.calls == closedCallCount, 'X-closed GUI continued rendering')
invoke('/oc', 'settings')
callbacks.d3d_present()
assert(ui.calls > closedCallCount, 'settings command did not reopen the GUI')

ui.failNextText = true
callbacks.d3d_present()
assert(ui.beginDepth == 0 and ui.comboDepth == 0, 'render failure leaked an ImGui stack')
assert(outputHas('Settings window closed after a rendering error.'), 'render failure was not isolated and explained')
local failedCallCount = ui.calls
callbacks.d3d_present()
assert(ui.calls == failedCallCount, 'failed GUI did not close itself')
invoke('/oc', 'settings')
ui.failNextBegin = true
callbacks.d3d_present()
assert(ui.beginDepth == 0, 'Begin failure incorrectly called End')
assert(outputHas('Settings window closed after a rendering error.'), 'Begin failure was not isolated and explained')
local beginFailedCallCount = ui.calls
callbacks.d3d_present()
assert(ui.calls == beginFailedCallCount, 'Begin-failed GUI did not close itself')
assert(#queued == 0, 'settings GUI queued a cast')
print('PASS OddCast native settings GUI and verified persistence contract')
""".replace("__ODDCAST_PATH__", ODDCAST_PATH.as_posix()).lstrip(),
        encoding="utf-8",
        newline="\n",
    )

    completed = subprocess.run(
        [luajit, str(driver)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (
        "PASS OddCast native settings GUI and verified persistence contract"
        in completed.stdout
    )


def test_control_center_uses_oddq_skin_and_manual_update_contract(tmp_path: Path) -> None:
    source = ODDCAST_PATH.read_text(encoding="utf-8")
    skin = (ODDCAST_PATH.parent / "ui_skin.lua").read_text(encoding="utf-8")
    checker = (ODDCAST_PATH.parent / "update_checker.lua").read_text(encoding="utf-8")

    assert "uiSkin.push_window(imgui)" in source
    assert "requestConfiguredAction('day')" in source
    assert "requestConfiguredAction('weak')" in source
    assert "activeSettings.onboardingComplete ~= true" in source
    assert "updateChecker.check(addon.version)" in source
    assert "0.063, 0.067, 0.067" in skin
    assert "0.098, 0.858, 1.000" in skin
    assert "transparent = { 0.000, 0.000, 0.000, 0.000 }" in skin
    assert "ImGuiCol_TitleBg', skin.colors.transparent" in skin
    assert "ImGuiCol_TitleBgActive', skin.colors.transparent" in skin
    assert "ImGuiCol_TitleBgCollapsed', skin.colors.transparent" in skin
    assert "ImGuiCol_ScrollbarBg" in skin
    assert "ImGuiCol_ScrollbarGrab" in skin
    assert "ImGuiCol_ScrollbarGrabHovered" in skin
    assert "ImGuiCol_ScrollbarGrabActive" in skin
    assert "ImGuiStyleVar_ScrollbarRounding" in skin
    assert "ImGuiStyleVar_ScrollbarSize" in skin
    assert "ImGuiStyleVar_ButtonTextAlign" in skin
    assert "ImGuiWindowFlags_AlwaysVerticalScrollbar" in source
    assert "ImGuiWindowFlags_NoCollapse" not in source
    assert "ODD_NETWORK_CALL: manual read-only GET" in checker

    luajit = shutil.which("luajit")
    assert luajit is not None
    driver = tmp_path / "update_checker_contract.lua"
    driver.write_text(
        (
        "local checker=dofile([[__CHECKER__]])\n"
        "local calls=0\n"
        "local function response() calls=calls+1; return '{\"tag_name\":\"OddCast-v1.4.0\"}',200 end\n"
        "local result=checker.check('1.3.0',{request=response})\n"
        "assert(calls==1 and result.status=='available' and result.latest_version=='1.4.0')\n"
        "local current=checker.check('1.4.0',{request=response})\n"
        "assert(current.status=='current')\n"
        "print('PASS OddCast manual update checker')\n"
        ).replace(
            "__CHECKER__", (ODDCAST_PATH.parent / "update_checker.lua").as_posix()
        ),
        encoding="utf-8",
        newline="\n",
    )
    completed = subprocess.run(
        [luajit, str(driver)], check=False, capture_output=True, text=True, timeout=10
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS OddCast manual update checker" in completed.stdout


def test_ui_skin_renders_each_sized_button_exactly_once(tmp_path: Path) -> None:
    luajit = shutil.which("luajit")
    assert luajit is not None
    skin_path = ODDCAST_PATH.parent / "ui_skin.lua"
    driver = tmp_path / "ui_skin_button_contract.lua"
    driver.write_text(
        (
            "local skin=dofile([[__SKIN__]])\n"
            "local calls=0\n"
            "local imgui={Button=function(label,size) calls=calls+1; "
            "assert(label=='Large'); assert(type(size)=='table' and size[1]==245 and size[2]==34); return false end}\n"
            "local clicked=skin.button(imgui,'Large',true,{245,34})\n"
            "assert(clicked==false and calls==1,'sized button rendered more than once')\n"
            "print('PASS OddCast sized button single-render contract')\n"
        ).replace("__SKIN__", skin_path.as_posix()),
        encoding="utf-8",
        newline="\n",
    )
    completed = subprocess.run(
        [luajit, str(driver)], check=False, capture_output=True, text=True, timeout=10
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS OddCast sized button single-render contract" in completed.stdout


def test_ui_skin_loads_exact_cjk_glyph_ranges(tmp_path: Path) -> None:
    luajit = shutil.which("luajit")
    assert luajit is not None
    skin_path = ODDCAST_PATH.parent / "ui_skin.lua"
    font_path = tmp_path / "test-font.ttf"
    font_path.write_bytes(b"font fixture")
    driver = tmp_path / "ui_skin_cjk_font_contract.lua"
    driver.write_text(
        r"""
local ffi = require('ffi')
local skin = dofile(arg[1])
local calls, pushed, popped = {}, nil, 0
local function includes(ranges, wanted)
    for index = 0, 510, 2 do
        local first = tonumber(ranges[index])
        if first == 0 then return false end
        local last = tonumber(ranges[index + 1])
        if wanted >= first and wanted <= last then return true end
    end
    return false
end
local imgui = {
    AddFontFromFileTTF=function(path, size, config, ranges)
        assert(path == arg[2] and size == 16 and config == nil and type(ranges) == 'cdata')
        calls[#calls + 1] = ranges
        return { call=#calls }
    end,
    PushFont=function(font) pushed=font end,
    PopFont=function() popped=popped+1 end,
}
local loaded = skin.load_locale_fonts(imgui, ffi, {
    ja={sample='日本語'}, zh={sample='简体中文'},
}, { ja={arg[2]}, zh={arg[2]} })
assert(#calls == 2 and loaded.ja ~= nil and loaded.zh ~= nil, 'both CJK fonts were not loaded')
assert(includes(calls[1], 0x65E5), 'Japanese day glyph was not requested')
assert(includes(calls[2], 0x7B80), 'Simplified Chinese glyph was not requested')
assert(skin.push_locale_font(imgui, loaded, 'zh') == true and pushed == loaded.zh.font, 'Chinese font was not pushed')
skin.pop_locale_font(imgui)
assert(popped == 1, 'CJK font stack was not balanced')
print('PASS OddCast exact CJK font contract')
""".lstrip(),
        encoding="utf-8",
        newline="\n",
    )
    completed = subprocess.run(
        [luajit, str(driver), str(skin_path), str(font_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS OddCast exact CJK font contract" in completed.stdout


def test_oddcast_compiles_under_luajit(tmp_path: Path) -> None:
    luajit = shutil.which("luajit")
    assert luajit is not None
    completed = subprocess.run(
        [luajit, "-b", str(ODDCAST_PATH), str(tmp_path / "oddcast.luac")],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    locales_completed = subprocess.run(
        [luajit, "-b", str(LOCALES_PATH), str(tmp_path / "locales.luac")],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert locales_completed.returncode == 0, (
        locales_completed.stdout + locales_completed.stderr
    )

    skin_completed = subprocess.run(
        [luajit, "-b", str(ODDCAST_PATH.parent / "ui_skin.lua"), str(tmp_path / "ui_skin.luac")],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert skin_completed.returncode == 0, skin_completed.stdout + skin_completed.stderr


def test_oddcast_locale_catalog_is_complete_and_format_safe(tmp_path: Path) -> None:
    luajit = shutil.which("luajit")
    assert luajit is not None
    locale_bytes = LOCALES_PATH.read_bytes()
    assert not locale_bytes.startswith(b"\xef\xbb\xbf")
    locale_text = locale_bytes.decode("utf-8")
    for mojibake_marker in ("Ã", "Â", "â€", "æ—", "ã‚", "�"):
        assert mojibake_marker not in locale_text
    driver = tmp_path / "locale_contract.lua"
    driver.write_text(
        r"""
local catalog = dofile(arg[1])
local expected = { 'en', 'fr', 'de', 'ja', 'es', 'zh' }
assert(#catalog.order == #expected, 'locale order count changed')
for index, code in ipairs(expected) do
    assert(catalog.order[index] == code, 'locale order changed')
    assert(type(catalog.names[code]) == 'string' and catalog.names[code] ~= '', 'locale name missing: ' .. code)
    assert(type(catalog.strings[code]) == 'table', 'locale table missing: ' .. code)
end

local formatArgs = {
    target_value={'<t>'}, chat_value={'On'}, language_value={'English'},
    target_updated={'<t>'}, chat_updated={'On'}, language_updated={'English'},
    cast_confirmed={'Fire V'}, tier_value={'Day', 'V', 5},
    tier_updated={'Day', 'V', 5}, error_no_ready_day={'Fire', 'Firesday'},
    day_submitted={'Firesday', 'Fire', 'Fire V'}, weak_unknown={'Crab', 'Thunder V'},
    weak_family={'Crab', 'Thunder V'}, request_queued={'', 'Weakness'},
    queue_pending={'Weakness', 'Crab'}, installed_version={'1.3.0'},
    update_available={'1.4.0'},
}

local nativeKeys = {
    'control_title', 'welcome_title', 'welcome_body', 'finish_setup',
    'cast_section', 'cast_explain', 'cast_day', 'cast_weak', 'queue_idle',
    'queue_pending', 'update_section', 'installed_version', 'check_updates',
    'update_current', 'update_available', 'update_unavailable',
}
for _, code in ipairs({ 'ja', 'zh' }) do
    for _, key in ipairs(nativeKeys) do
        assert(catalog.strings[code][key] ~= catalog.strings.en[key], code .. ' retained English UI text: ' .. key)
    end
end
assert(catalog.strings.zh.day == '日属性', 'Chinese day label is not native terminology')
assert(not string.find(catalog.strings.zh.help_day, '曜日', 1, true), 'Chinese help contains Japanese terminology')

for key, english in pairs(catalog.strings.en) do
    assert(type(english) == 'string' and english ~= '', 'empty English locale key: ' .. key)
    for _, code in ipairs(expected) do
        local value = catalog.strings[code][key]
        assert(type(value) == 'string' and value ~= '', code .. ' missing locale key: ' .. key)
        local args = formatArgs[key]
        if args ~= nil then
            local ok, rendered = pcall(string.format, value, unpack(args))
            assert(ok and type(rendered) == 'string' and rendered ~= '', code .. ' invalid format string: ' .. key)
        end
    end
end

for _, code in ipairs(expected) do
    for key in pairs(catalog.strings[code]) do
        assert(catalog.strings.en[key] ~= nil, code .. ' has unknown locale key: ' .. key)
    end
end
print('PASS OddCast locale catalog contract')
""".lstrip(),
        encoding="utf-8",
        newline="\n",
    )
    completed = subprocess.run(
        [luajit, str(driver), str(LOCALES_PATH)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS OddCast locale catalog contract" in completed.stdout
