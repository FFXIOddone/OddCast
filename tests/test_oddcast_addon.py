from pathlib import Path
import os
import re
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
ODDCAST_PATH = ROOT / "addons" / "oddcast" / "oddcast.lua"
ODDCAST_DIR = ODDCAST_PATH.parent
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
                "local mainJob, mainLevel, subJob, subLevel = 4, 75, 1, 37",
                "local known = { [146]=1, [167]=true, [171]=true, [172]=true }",
                "local timers = {}",
                "local currentMP = 999",
                "local chatAvailable = true",
                "local signatureAddress = 0",
                "local rawTime = (80002 * 3456) - 92514960",
                "local mutateTargetOnTimer = false",
                "local resources = {}",
                "local function spell(id, name, mp, blmLevel)",
                "    resources[id] = { Name={name}, ManaCost=mp, LevelRequired={ [5]=blmLevel } }",
                "end",
                "spell(146, 'Fire III', 63, 62)",
                "spell(167, 'Thunder IV', 195, 75)",
                "spell(171, 'Water III', 46, 55)",
                "spell(172, 'Water IV', 99, 70)",
                "local originalPrint = print",
                "print = function(value) output[#output + 1] = tostring(value); originalPrint(value) end",
                "T = function(value) return value end",
                "package.preload['common'] = function() return true end",
                "package.preload['settings'] = function()",
                "    local value = { target='<t>' }",
                "    return { load=function() return value end, save=function() return true end, register=function() return true end }",
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
                "}",
                "local target = { GetIsSubTargetActive=function() return 0 end, GetTargetIndex=function() return targetIndex end }",
                "local entity = { GetSpawnFlags=function() return 0x10 end, GetName=function() return targetName end, GetServerId=function() return targetServerId end }",
                "local player = {",
                "    GetMainJob=function() return mainJob end, GetMainJobLevel=function() return mainLevel end,",
                "    GetSubJob=function() return subJob end, GetSubJobLevel=function() return subLevel end,",
                "    HasSpell=function(_, id) return known[id] end,",
                "}",
                "local party = { GetMemberMP=function() return currentMP end, GetMemberZone=function() return targetZone end }",
                "local recast = { GetSpellTimer=function(_, id)",
                "    if mutateTargetOnTimer then targetIndex=400; targetName='Changed Rabbit'; mutateTargetOnTimer=false end",
                "    return timers[id] or 0",
                "end }",
                "local memory = {",
                "    GetTarget=function() return target end, GetEntity=function() return entity end,",
                "    GetPlayer=function() return player end, GetParty=function() return party end,",
                "    GetRecast=function() return recast end,",
                "}",
                "local resourceManager = { GetSpellById=function(_, id) return resources[id] end }",
                "local chatManager = { QueueCommand=function(_, mode, command) queued[#queued + 1]={mode=mode, command=command} end }",
                "AshitaCore = {",
                "    GetMemoryManager=function() return memory end,",
                "    GetResourceManager=function() return resourceManager end,",
                "    GetChatManager=function() if chatAvailable then return chatManager end return nil end,",
                "}",
                "dofile(ODDCAST_PATH)",
                "local function invoke(prefix, action)",
                "    local event={ command={ args=function() return {prefix, action} end }, blocked=false }",
                "    callbacks.command(event)",
                "    assert(event.blocked == true, 'OddCast command was not blocked')",
                "end",
                "callbacks.load()",
                "invoke('/oc', 'day')",
                "assert(#queued == 0, 'failed Vana signature scan cast instead of failing closed')",
                "signatureAddress = 1000",
                "invoke('/oc', 'day')",
                "assert(queued[1].mode == 1, 'day did not use the typed command queue')",
                "assert(queued[1].command == '/ma \"Water IV\" <t>', 'day did not choose highest ready Watersday tier')",
                "rawTime = 0",
                "invoke('/oc', 'day')",
                "assert(#queued == 1, 'zero Vana time cast instead of failing closed')",
                "rawTime = (80002 * 3456) - 92514960",
                "mainJob, mainLevel, subJob, subLevel = 1, 75, 4, 70",
                "invoke('/oddcast', 'day')",
                "assert(queued[2].command == '/ma \"Water IV\" <t>', 'day rejected a spell available exactly at subjob level')",
                "subLevel = 69",
                "invoke('/oc', 'day')",
                "assert(queued[3].command == '/ma \"Water III\" <t>', 'day ignored the active subjob level boundary')",
                "mainJob, mainLevel, subJob, subLevel = 4, 75, 1, 37",
                "timers[172] = 1",
                "invoke('/oc', 'day')",
                "assert(queued[4].command == '/ma \"Water III\" <t>', 'day ignored a higher-tier spell recast')",
                "timers[172] = nil",
                "currentMP = 50",
                "invoke('/oc', 'day')",
                "assert(queued[5].command == '/ma \"Water III\" <t>', 'day ignored insufficient MP for the higher tier')",
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
                "local known, timers, mutateTarget = {}, {}, false",
                "local sourceSha = 'sha256:' .. string.rep('a', 64)",
                "local fileSha = 'sha256:' .. string.rep('b', 64)",
                "local elements = { 'Fire', 'Ice', 'Wind', 'Earth', 'Lightning', 'Water' }",
                "local resources = {}",
                "local function spell(id, name)",
                "    resources[id] = { Name={name}, ManaCost=1, LevelRequired={ [5]=1 } }",
                "end",
                "spell(147, 'Fire IV')",
                "spell(148, 'Fire V')",
                "spell(153, 'Blizzard V')",
                "spell(158, 'Aero V')",
                "spell(163, 'Stone V')",
                "spell(168, 'Thunder V')",
                "spell(173, 'Water V')",
                "T = function(value) return value end",
                "package.preload['common'] = function() return true end",
                "package.preload['settings'] = function()",
                "    local value = { target='<t>' }",
                "    return { load=function() return value end, save=function() return true end, register=function() return true end }",
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
                "local party = { GetMemberMP=function() return 9999 end, GetMemberZone=function() return targetZone end }",
                "local recast = { GetSpellTimer=function(_, id)",
                "    if mutateTarget then",
                "        targetServerId, targetZone, mutateTarget = 654321, 101, false",
                "    end",
                "    return timers[id] or 0",
                "end }",
                "local memory = {",
                "    GetTarget=function() return target end, GetEntity=function() return entity end,",
                "    GetPlayer=function() return player end, GetParty=function() return party end,",
                "    GetRecast=function() return recast end,",
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
                "    known = { [147]=true, [148]=true, [153]=true, [158]=true, [163]=true, [168]=true, [173]=true }",
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
                "local dominant = { 10000, -5000, -5000, -5000, -5000, -5000, 0, 1, 1, 1, 1, 1 }",
                "reset(indexData(dominant))",
                "invoke('/oc', 'weak')",
                "assert(#queued == 1 and queued[1].command == '/ma \"Fire V\" <t>', 'exact dominant lookup did not choose Fire V')",
                "invoke('/oddcast', 'weakness')",
                "assert(#queued == 2 and queued[2].command == '/ma \"Fire V\" <t>', 'weakness alias did not choose Fire V')",
                "assert(loadCounts['fixture/weakness_data.lua'] == 1, 'weakness index was not cached')",
                "timers[148] = 1",
                "invoke('/oc', 'weak')",
                "assert(#queued == 3 and queued[3].command == '/ma \"Fire IV\" <t>', 'weakness did not use the highest ready tier per element')",
                "local sawClaim = false",
                "for _, line in ipairs(output) do if string.find(line, 'typical family baseline', 1, true) then sawClaim=true end end",
                "assert(sawClaim, 'success output omitted the typical family boundary')",
                "reset(indexData(dominant))",
                "targetZone = 199",
                "invoke('/oc', 'weak')",
                "assert(#queued == 1 and queued[1].command == '/ma \"Fire V\" <t>', 'zone changed the mob-family weakness lookup')",
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
                "local tradeoff = { 10000, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0 }",
                "reset(indexData(tradeoff))",
                "known = { [148]=true, [153]=true }",
                "invoke('/oc', 'weak')",
                "assert(#queued == 1 and queued[1].command == '/ma \"Blizzard V\" <t>', 'best resistance rank did not win the potency tradeoff')",
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
                "T = function(value) return value end",
                "package.preload['common'] = function() return true end",
                "package.preload['settings'] = function() local value={target='<t>'}; return {load=function() return value end,save=function() return true end,register=function() return true end} end",
                "package.loaded['ffi'] = nil",
                "package.preload['ffi'] = function() return {cdef=function() end,cast=function() error('unexpected <bt> lookup') end} end",
                "package.preload['chat'] = function() return { header=function(v) return '['..v..'] ' end, message=function(v) return v end, error=function(v) return v end } end",
                "addon = { path=[[" + ODDCAST_DIR.as_posix() + "/]] }",
                "ashita = { events={register=function(name, _, cb) callbacks[name]=cb end}, memory={find=function() return 0 end, read_uint32=function() return 0 end} }",
                "local resources = {}",
                "-- Deliberately synthetic identities prove weakness is keyed by the global mob name, not a zone spawn row.",
                "local liveName, liveServerId, liveZone = 'Damselfly', 17227777, 119",
                "for _, row in ipairs({{148,'Fire V'},{153,'Blizzard V'},{158,'Aero V'},{163,'Stone V'},{168,'Thunder V'},{173,'Water V'}}) do resources[row[1]]={Name={row[2]},ManaCost=1,LevelRequired={[5]=1}} end",
                "local target={GetIsSubTargetActive=function() return 0 end,GetTargetIndex=function() return 1 end}",
                "local entity={GetSpawnFlags=function() return 0x10 end,GetName=function() return liveName end,GetServerId=function() return liveServerId end}",
                "local player={GetMainJob=function() return 4 end,GetMainJobLevel=function() return 99 end,GetSubJob=function() return 1 end,GetSubJobLevel=function() return 49 end,HasSpell=function(_, id) return resources[id] ~= nil end}",
                "local party={GetMemberMP=function() return 9999 end,GetMemberZone=function() return liveZone end}",
                "local recast={GetSpellTimer=function() return 0 end}",
                "local memory={GetTarget=function() return target end,GetEntity=function() return entity end,GetPlayer=function() return player end,GetParty=function() return party end,GetRecast=function() return recast end}",
                "local resourceManager={GetSpellById=function(_, id) return resources[id] end}",
                "local chatManager={QueueCommand=function(_, mode, command) queued[#queued+1]={mode=mode,command=command} end}",
                "AshitaCore={GetMemoryManager=function() return memory end,GetResourceManager=function() return resourceManager end,GetChatManager=function() return chatManager end}",
                "dofile(ODDCAST_PATH)",
                "local event={command={args=function() return {'/oc','weak'} end},blocked=false}",
                "callbacks.command(event)",
                "assert(event.blocked == true, 'real-data command was not consumed')",
                "assert(#queued == 1, 'Meriphataud Damselfly did not produce exactly one queue')",
                "assert(queued[1].mode == 1 and queued[1].command == '/ma \"Blizzard V\" <t>', 'Damselfly did not use the global Fly weakness profile')",
                "liveName, liveServerId, liveZone = 'Goblin Ambusher', 999999, 1",
                "callbacks.command({command={args=function() return {'/oc','weak'} end},blocked=false})",
                "assert(#queued == 2 and queued[2].command == '/ma \"Thunder V\" <t>', 'Goblin did not use the global Goblin weakness profile')",
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


def test_oddcast_text_target_settings_bind_selection_and_queued_token(
    tmp_path: Path,
) -> None:
    luajit = shutil.which("luajit")
    assert luajit is not None
    addon_text = ODDCAST_PATH.read_text(encoding="utf-8")
    assert "require('imgui')" not in addon_text
    assert "target = '<t>'" in addon_text

    driver = tmp_path / "oddcast_target_settings_contract.lua"
    driver.write_text(
        "\n".join(
            (
                "local ODDCAST_PATH = [[" + ODDCAST_PATH.as_posix() + "]]",
                "local realDofile = dofile",
                "local callbacks, queued, output = {}, {}, {}",
                "local activeSettings, settingsCallback = {target='<t>'}, nil",
                "local saveCount, saveAllowed = 0, true",
                "local mainIndex, mainServerId, mainName = 321, 111111, 'Main Rabbit'",
                "local btIndex, btServerId, btName = 322, 222222, 'Battle Rabbit'",
                "local btPresent, btSignatureAddress = true, 0",
                "local subTargetActive, mutateBattleOnTimer = 0, false",
                "local zone = 100",
                "local rawTime = (80002 * 3456) - 92514960",
                "local sourceSha = 'sha256:' .. string.rep('a', 64)",
                "local elements = {'Fire','Ice','Wind','Earth','Lightning','Water'}",
                "local fireDominant = {10000,-5000,-5000,-5000,-5000,-5000,0,1,1,1,1,1}",
                "local iceDominant = {-5000,10000,-5000,-5000,-5000,-5000,1,0,1,1,1,1}",
                "local dataFiles = {",
                "  ['fixture/weakness_data.lua']={schema=2,sourceSha256=sourceSha,elements=elements,profiles={[7]=fireDominant,[8]=iceDominant},names={['main rabbit']=7,['battle rabbit']=8},familyPrefixes={['rabbit']=7}},",
                "}",
                "local resources = {}",
                "for _, row in ipairs({{148,'Fire V'},{153,'Blizzard V'},{158,'Aero V'},{163,'Stone V'},{168,'Thunder V'},{173,'Water V'}}) do",
                "  resources[row[1]]={Name={row[2]},ManaCost=1,LevelRequired={[5]=1}}",
                "end",
                "local originalPrint = print",
                "print=function(value) output[#output+1]=tostring(value); originalPrint(value) end",
                "T=function(value) return value end",
                "package.preload['common']=function() return true end",
                "package.preload['chat']=function() return {header=function(v) return '['..v..'] ' end,message=function(v) return v end,error=function(v) return v end} end",
                "package.preload['settings']=function() return {",
                "  load=function() return activeSettings end,",
                "  save=function() saveCount=saveCount+1; return saveAllowed end,",
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
                "}}",
                "local target={GetIsSubTargetActive=function() return subTargetActive end,GetTargetIndex=function() return mainIndex end}",
                "local entity={",
                "  GetSpawnFlags=function(_,index) if index==mainIndex or index==btIndex then return 0x10 end return 0 end,",
                "  GetName=function(_,index) if index==mainIndex then return mainName end if index==btIndex then return btName end return '' end,",
                "  GetServerId=function(_,index) if index==mainIndex then return mainServerId end if index==btIndex then return btServerId end return 0 end,",
                "}",
                "local player={GetMainJob=function() return 4 end,GetMainJobLevel=function() return 99 end,GetSubJob=function() return 1 end,GetSubJobLevel=function() return 49 end,HasSpell=function(_,id) return resources[id] ~= nil end}",
                "local party={GetMemberMP=function() return 9999 end,GetMemberZone=function() return zone end}",
                "local recast={GetSpellTimer=function() if mutateBattleOnTimer then btIndex,btServerId,btName,mutateBattleOnTimer=323,333333,'Changed Rabbit',false end return 0 end}",
                "local memory={GetTarget=function() return target end,GetEntity=function() return entity end,GetPlayer=function() return player end,GetParty=function() return party end,GetRecast=function() return recast end}",
                "local resourceManager={GetSpellById=function(_,id) return resources[id] end}",
                "local chatManager={QueueCommand=function(_,mode,command) queued[#queued+1]={mode=mode,command=command} end}",
                "AshitaCore={GetMemoryManager=function() return memory end,GetResourceManager=function() return resourceManager end,GetChatManager=function() return chatManager end}",
                "addon={path='fixture/'}",
                "realDofile(ODDCAST_PATH)",
                "local function invoke(...) local values={...}; local event={command={args=function() return values end},blocked=false}; callbacks.command(event); assert(event.blocked==true,'OddCast command was not blocked') end",
                "invoke('/oc','settings')",
                "assert(string.find(output[#output],'Target token: <t>',1,true),'settings did not show default <t>')",
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
                "invoke('/oc','day')",
                "assert(#queued==2 and queued[2].command=='/ma \"Water V\" <bt>','day did not use the configured <bt> resolver and queue token')",
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
                "settingsCallback({target='<stnpc>'})",
                "invoke('/oc','weak')",
                "assert(#queued==3,'corrupt persisted target token queued a spell')",
                "invoke('/oc','settings')",
                "assert(string.find(output[#output],'target setting is invalid',1,true),'invalid persisted setting was not explained')",
                "invoke('/oc','target','<t>')",
                "assert(saveCount==3,'valid command did not repair an invalid persisted setting')",
                "saveAllowed=false",
                "invoke('/oc','target','<bt>')",
                "assert(activeSettings.target=='<t>' and saveCount==4,'failed settings save did not roll back')",
                "print('PASS OddCast text-only target settings and exact token binding')",
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
        "PASS OddCast text-only target settings and exact token binding"
        in completed.stdout
    )


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
