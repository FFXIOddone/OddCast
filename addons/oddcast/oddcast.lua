-- SPDX-License-Identifier: GPL-3.0-or-later
-- Copyright (c) 2026 Oddone
-- Modified for OddCast on 2026-08-12; see THIRD_PARTY_NOTICES.md.

addon.name = 'oddcast';
addon.author = 'Oddone';
addon.version = '1.4.0';
addon.desc = 'Selects a ready nuke for the current Vana day, a typical weakness, or an unknown-target fallback.';

require('common');
local bit = require('bit');
local chat = require('chat');
local ffi = require('ffi');
local imgui = require('imgui');
local settings = require('settings');

local defaultSettings = T{
    target = '<t>',
    dayTierCeiling = 5,
    weaknessTierCeiling = 5,
    showRoutineChat = false,
    language = 'en',
    onboardingComplete = false,
};
local activeSettings = settings.load(defaultSettings);
local settingsWindowOpen = { false };
local updateState = { status='not_checked' };
settings.register('settings', 'oddcast_settings_cb', function(updatedSettings)
    activeSettings = updatedSettings;
end);

pcall(ffi.cdef, [[
    typedef struct {
        uint32_t GuideNo;
        uint32_t UniqueNo;
    } OddCastCharId;

    typedef struct {
        uint8_t padding00[116];
        OddCastCharId id;
    } OddCastBattleActor;

    typedef OddCastBattleActor* (__stdcall* OddCastSeekBattleActor_f)(void);
]]);

-- Provenance: Vana'diel-time signature and relative pointer-chain constants were
-- adapted from LuAshitacast by ThornyFFXI (MIT). See THIRD_PARTY_NOTICES.md.
local VANA_TIME_SIGNATURE = 'B0015EC390518B4C24088D4424005068';
-- Provenance: <bt> signature and FFI actor layout adapted from FancyChat's
-- targets.lua (Ashita Development Team, GPL-3.0-or-later). See THIRD_PARTY_NOTICES.md.
local BATTLE_TARGET_SIGNATURE = '66A1????????83EC186685C053565774??0FBFC08B0C85';
local VANA_TIME_EPOCH_OFFSET = 92514960;
local VANA_DAY_SECONDS = 3456;

local WEAKNESS_SCHEMA = 2;
local WEAKNESS_INDEX_FILE = 'weakness_data.lua';
local weaknessIndex = nil;

local PENDING_REQUEST_TTL_SECONDS = 15.0;
local POST_CAST_LOCK_SECONDS = 3.1;
local CAST_COUNT_STALE_SECONDS = 0.10;
local START_ACK_SECONDS = 2.0;
local RETRY_LOCK_SECONDS = 1.1;
local MAX_SUBMISSIONS = 4;
local PRESENT_THROTTLE_SECONDS = 0.05;
local MAX_SERVER_ID = 4294967295;
local pendingRequest = nil;
local lastPresentAt = nil;
local resolvedTargetIndexByServerId = {};

local dayElements = {
    { day = 'Firesday', element = 'Fire' },
    { day = 'Earthsday', element = 'Earth' },
    { day = 'Watersday', element = 'Water' },
    { day = 'Windsday', element = 'Wind' },
    { day = 'Iceday', element = 'Ice' },
    { day = 'Lightningday', element = 'Lightning' },
    { day = 'Lightsday', element = 'Light' },
    { day = 'Darksday', element = 'Dark' },
};

-- PC base powers mirror the checked-in CatsEye damage-spell table.  This is
-- deliberately limited to single-target tier-line nukes.  AoE, ancient magic,
-- helix damage-over-time, and gear/buff-specific spells are not comparable as
-- one safe automatic choice.
local spells = {
    { id=144, name='Fire',       element='Fire',      tier=1, power=55,  weak=true },
    { id=145, name='Fire II',    element='Fire',      tier=2, power=160, weak=true },
    { id=146, name='Fire III',   element='Fire',      tier=3, power=290, weak=true },
    { id=147, name='Fire IV',    element='Fire',      tier=4, power=520, weak=true },
    { id=148, name='Fire V',     element='Fire',      tier=5, power=800, weak=true },
    { id=149, name='Blizzard',   element='Ice',       tier=1, power=70,  weak=true },
    { id=150, name='Blizzard II',element='Ice',       tier=2, power=180, weak=true },
    { id=151, name='Blizzard III',element='Ice',      tier=3, power=320, weak=true },
    { id=152, name='Blizzard IV',element='Ice',       tier=4, power=560, weak=true },
    { id=153, name='Blizzard V', element='Ice',       tier=5, power=850, weak=true },
    { id=154, name='Aero',       element='Wind',      tier=1, power=40,  weak=true },
    { id=155, name='Aero II',    element='Wind',      tier=2, power=140, weak=true },
    { id=156, name='Aero III',   element='Wind',      tier=3, power=260, weak=true },
    { id=157, name='Aero IV',    element='Wind',      tier=4, power=480, weak=true },
    { id=158, name='Aero V',     element='Wind',      tier=5, power=750, weak=true },
    { id=159, name='Stone',      element='Earth',     tier=1, power=10,  weak=true },
    { id=160, name='Stone II',   element='Earth',     tier=2, power=100, weak=true },
    { id=161, name='Stone III',  element='Earth',     tier=3, power=200, weak=true },
    { id=162, name='Stone IV',   element='Earth',     tier=4, power=400, weak=true },
    { id=163, name='Stone V',    element='Earth',     tier=5, power=650, weak=true },
    { id=164, name='Thunder',    element='Lightning', tier=1, power=85,  weak=true },
    { id=165, name='Thunder II', element='Lightning', tier=2, power=200, weak=true },
    { id=166, name='Thunder III',element='Lightning', tier=3, power=350, weak=true },
    { id=167, name='Thunder IV', element='Lightning', tier=4, power=600, weak=true },
    { id=168, name='Thunder V',  element='Lightning', tier=5, power=900, weak=true },
    { id=169, name='Water',      element='Water',     tier=1, power=25,  weak=true },
    { id=170, name='Water II',   element='Water',     tier=2, power=120, weak=true },
    { id=171, name='Water III',  element='Water',     tier=3, power=230, weak=true },
    { id=172, name='Water IV',   element='Water',     tier=4, power=440, weak=true },
    { id=173, name='Water V',    element='Water',     tier=5, power=700, weak=true },
    -- Dia and Bio are the explicit Lightsday and Darksday families. They use
    -- different stat/formula families and are not considered by weakness mode.
    { id=23,  name='Dia',        element='Light',     tier=1, power=1,   weak=false },
    { id=24,  name='Dia II',     element='Light',     tier=2, power=4,   weak=false },
    { id=25,  name='Dia III',    element='Light',     tier=3, power=16,  weak=false },
    { id=230, name='Bio',        element='Dark',      tier=1, power=10,  weak=false },
    { id=231, name='Bio II',     element='Dark',      tier=2, power=50,  weak=false },
    { id=232, name='Bio III',    element='Dark',      tier=3, power=100, weak=false },
};

local vanaTimeAddress = nil;
local battleTargetAddress = nil;

local weaknessElements = { 'Fire', 'Ice', 'Wind', 'Earth', 'Lightning', 'Water' };
local tierRoman = { 'I', 'II', 'III', 'IV', 'V' };
local tierInputs = {
    ['1'] = 1, ['i'] = 1,
    ['2'] = 2, ['ii'] = 2,
    ['3'] = 3, ['iii'] = 3,
    ['4'] = 4, ['iv'] = 4,
    ['5'] = 5, ['v'] = 5,
    ['clear'] = 5,
};

local function safe(defaultValue, callback)
    local ok, value = pcall(callback);
    if ok and value ~= nil then
        return value;
    end
    return defaultValue;
end

local function loadSibling(name)
    local loaded = safe(nil, function() return dofile(addon.path .. name); end);
    if loaded ~= nil then return loaded; end
    return safe({}, function()
        local source = debug.getinfo(1, 'S').source or '';
        local path = string.match(source, '^@(.+[\\/])[^\\/]+$');
        return dofile(path .. name);
    end);
end

local uiSkin = loadSibling('ui_skin.lua');
local updateChecker = loadSibling('update_checker.lua');

local localeBundle = safe(nil, function()
    return dofile(addon.path .. 'locales.lua');
end);
if localeBundle == nil then
    localeBundle = safe({}, function()
        local source = debug.getinfo(1, 'S').source or '';
        local path = string.match(source, '^@(.+[\\/])[^\\/]+$');
        return dofile(path .. 'locales.lua');
    end);
end
local localeOrder = type(localeBundle.order) == 'table' and localeBundle.order or { 'en' };
local localeNames = type(localeBundle.names) == 'table' and localeBundle.names or { en = 'English' };
local localeStrings = type(localeBundle.strings) == 'table' and localeBundle.strings or { en = {} };
local localeFonts = safe({}, function()
    if uiSkin.load_locale_fonts == nil then return {}; end
    return uiSkin.load_locale_fonts(imgui, ffi, localeStrings);
end);
local guiLocaleActive = false;

local function isSupportedLanguage(value)
    return type(value) == 'string'
        and localeNames[value] ~= nil
        and type(localeStrings[value]) == 'table';
end

local function currentLanguage()
    local value = activeSettings and activeSettings.language or nil;
    if isSupportedLanguage(value) then
        return value;
    end
    return 'en';
end

local function tx(key, ...)
    local args = { ... };
    local language = currentLanguage();
    if (language == 'ja' or language == 'zh')
        and (not guiLocaleActive or localeFonts[language] == nil) then
        language = 'en';
    end
    local selected = localeStrings[language] or {};
    local english = localeStrings.en or {};
    local value = selected[key] or english[key] or key;
    if select('#', ...) == 0 then
        return value;
    end
    local ok, formatted = pcall(string.format, value, unpack(args));
    if ok then
        return formatted;
    end
    local fallback = english[key] or key;
    return safe(fallback, function() return string.format(fallback, unpack(args)); end);
end

local function message(text, isError)
    local formatter = isError and chat.error or chat.message;
    print(chat.header('OddCast') .. formatter(text));
end

local function beginUpdateInstall()
    local started, resultPath = updateChecker.begin_install(addon.version, addon.path);
    if not started then
        updateState = { status='install_error', detail=tostring(resultPath or 'unable to start updater') };
        return;
    end
    updateState.status = 'installing';
    updateState.result_path = resultPath;
    updateState.started_at = os.time();
end

local function processUpdateInstall()
    if updateState.status ~= 'installing' or updateState.result_path == nil then return; end
    local result = updateChecker.poll_install(updateState.result_path);
    if result == nil then
        if os.time() - (updateState.started_at or os.time()) > 180 then
            updateState = { status='install_error', detail='The updater did not finish within three minutes.' };
            message(tx('update_failed', updateState.detail), true);
        end
        return;
    end
    if result.status == 'success' then
        updateState = { status='reloading' };
        local chatManager = safe(nil, function() return AshitaCore:GetChatManager(); end);
        if chatManager ~= nil then chatManager:QueueCommand(-1, '/addon reload oddcast'); end
    elseif result.status == 'current' then
        updateState = { status='current', latest_version=result.detail };
    else
        updateState = { status='install_error', detail=result.detail };
        message(tx('update_failed', result.detail), true);
    end
end

local function routineMessage(text)
    if activeSettings ~= nil and activeSettings.showRoutineChat == true then
        message(text, false);
    end
end

local function isInteger(value)
    return type(value) == 'number'
        and value == value
        and value > -math.huge
        and value < math.huge
        and value == math.floor(value);
end

local function isPositiveInteger(value)
    return isInteger(value) and value > 0;
end

local function isNonNegativeInteger(value)
    return isInteger(value) and value >= 0;
end

local function isSha256(value)
    return type(value) == 'string'
        and #value == 71
        and string.match(value, '^sha256:%x+$') ~= nil;
end

local function normalizeMobName(value)
    return string.lower(tostring(value or ''))
        :gsub('_', ' ')
        :gsub('%s+', ' ')
        :gsub('^%s+', '')
        :gsub('%s+$', '');
end

local function addonFile(relativePath)
    local base = tostring(addon.path or '');
    if base == '' then
        return nil;
    end
    local last = string.sub(base, -1);
    if last == '/' or last == '\\' then
        return base .. relativePath;
    end
    return base .. '/' .. relativePath;
end

local function validProfile(profile)
    if type(profile) ~= 'table' then
        return false;
    end
    local count = 0;
    for index, value in pairs(profile) do
        count = count + 1;
        if not isInteger(index)
            or index < 1
            or index > 12
            or not isInteger(value)
            or (index >= 7 and (value < -3 or value > 11))
        then
            return false;
        end
    end
    return count == 12;
end

local function loadWeaknessIndex()
    if weaknessIndex ~= nil then
        return weaknessIndex, nil;
    end

    local path = addonFile(WEAKNESS_INDEX_FILE);
    if path == nil then
        return nil, tx('error_weakness_data');
    end
    local ok, data = pcall(dofile, path);
    if not ok or type(data) ~= 'table' then
        return nil, tx('error_weakness_data');
    end
    if data.schema ~= WEAKNESS_SCHEMA
        or not isSha256(data.sourceSha256)
        or type(data.elements) ~= 'table'
        or type(data.profiles) ~= 'table'
        or type(data.names) ~= 'table'
        or type(data.familyPrefixes) ~= 'table'
    then
        return nil, tx('error_weakness_data');
    end
    local elementCount = 0;
    for key in pairs(data.elements) do
        elementCount = elementCount + 1;
        if not isPositiveInteger(key) or key > #weaknessElements then
            return nil, tx('error_weakness_data');
        end
    end
    for index, element in ipairs(weaknessElements) do
        if data.elements[index] ~= element then
            return nil, tx('error_weakness_data');
        end
    end
    if elementCount ~= #weaknessElements then
        return nil, tx('error_weakness_data');
    end
    for profileId, profile in pairs(data.profiles) do
        if not isNonNegativeInteger(profileId) or not validProfile(profile) then
            return nil, tx('error_weakness_data');
        end
    end
    for name, profileId in pairs(data.names) do
        if type(name) ~= 'string' or name == '' or normalizeMobName(name) ~= name
            or not isNonNegativeInteger(profileId) or data.profiles[profileId] == nil
        then
            return nil, tx('error_weakness_data');
        end
    end
    for prefix, profileId in pairs(data.familyPrefixes) do
        if type(prefix) ~= 'string' or prefix == '' or normalizeMobName(prefix) ~= prefix
            or not isNonNegativeInteger(profileId) or data.profiles[profileId] == nil
        then
            return nil, tx('error_weakness_data');
        end
    end

    weaknessIndex = data;
    return weaknessIndex, nil;
end

local function configuredTargetToken()
    local token = activeSettings and activeSettings.target or nil;
    if token == '<t>' or token == '<bt>' then
        return token, nil;
    end
    return nil, tx('error_target_setting');
end

local function configuredRoutineChat()
    local value = activeSettings and activeSettings.showRoutineChat;
    if type(value) == 'boolean' then
        return value, nil;
    end
    return nil, tx('error_chat_setting');
end

local function configuredLanguage()
    local value = activeSettings and activeSettings.language or nil;
    if isSupportedLanguage(value) then
        return value, nil;
    end
    return nil, tx('error_language_setting');
end

local function resolvedTargetServerId(value)
    local token = tostring(value or '');
    if string.match(token, '^%d+$') == nil then
        return nil;
    end
    local serverId = tonumber(token);
    if not isPositiveInteger(serverId) or serverId > MAX_SERVER_ID then
        return nil;
    end
    return serverId;
end

local function requestTargetToken(value)
    if value == nil then
        return configuredTargetToken();
    end
    local token = tostring(value);
    if string.lower(token) == '[t]' then
        return '[t]', nil;
    end
    local serverId = resolvedTargetServerId(token);
    if serverId ~= nil then
        return tostring(serverId), nil;
    end
    return nil, tx('error_one_shot');
end

local function configuredTierCeiling(action)
    local key = action == 'day' and 'dayTierCeiling' or 'weaknessTierCeiling';
    local value = activeSettings and activeSettings[key] or nil;
    if isInteger(value) and value >= 1 and value <= 5 then
        return value, nil;
    end
    return nil, tx('error_tier');
end

local function battleTargetIndex()
    if battleTargetAddress == nil or battleTargetAddress <= 0 then
        local found = tonumber(safe(0, function()
            return ashita.memory.find('FFXiMain.dll', 0, BATTLE_TARGET_SIGNATURE, 0, 0);
        end)) or 0;
        if found > 0 then
            battleTargetAddress = found;
        end
    end
    if battleTargetAddress == nil or battleTargetAddress <= 0 then
        return nil, nil, tx('error_target');
    end

    local ok, actor = pcall(function()
        local seekBattleActor = ffi.cast('OddCastSeekBattleActor_f', battleTargetAddress);
        return seekBattleActor();
    end);
    if not ok then
        battleTargetAddress = nil;
        return nil, nil, tx('error_target');
    end
    if actor == nil then
        return nil, nil, tx('error_target');
    end

    local index = tonumber(safe(nil, function() return actor.id.GuideNo; end));
    local serverId = tonumber(safe(nil, function() return actor.id.UniqueNo; end));
    if not isPositiveInteger(index) then
        return nil, nil, tx('error_target');
    end
    return index, serverId, nil;
end

local function targetIndexForToken(memory, token)
    if token == '<bt>' then
        return battleTargetIndex();
    end

    local serverId = resolvedTargetServerId(token);
    if serverId ~= nil then
        local entity = safe(nil, function() return memory:GetEntity(); end);
        if entity == nil then
            return nil, nil, tx('error_runtime');
        end
        local cachedIndex = resolvedTargetIndexByServerId[serverId];
        if isPositiveInteger(cachedIndex) then
            local cachedServerId = tonumber(safe(0, function()
                return entity:GetServerId(cachedIndex);
            end)) or 0;
            if cachedServerId == serverId then
                return cachedIndex, serverId, nil;
            end
            resolvedTargetIndexByServerId[serverId] = nil;
        end

        local mapSize = tonumber(safe(0, function() return entity:GetEntityMapSize(); end)) or 0;
        if not isPositiveInteger(mapSize) then
            return nil, nil, tx('error_runtime');
        end
        for index = 1, mapSize - 1 do
            local candidateServerId = tonumber(safe(0, function()
                return entity:GetServerId(index);
            end)) or 0;
            if candidateServerId == serverId then
                resolvedTargetIndexByServerId[serverId] = index;
                return index, serverId, nil;
            end
        end
        return nil, nil, tx('error_target');
    end

    local target = safe(nil, function() return memory:GetTarget(); end);
    if target == nil then
        return nil, nil, tx('error_runtime');
    end
    local subTargetActive = safe(nil, function() return target:GetIsSubTargetActive(); end);
    if subTargetActive == nil then
        return nil, nil, tx('error_target');
    end
    local hasSubTarget = subTargetActive == true or (tonumber(subTargetActive) or 0) ~= 0;
    if token ~= '<t>' and token ~= '[t]' then
        return nil, nil, tx('error_target');
    end
    if token == '<t>' and hasSubTarget then
        return nil, nil, tx('error_subtarget');
    end

    local slot = token == '[t]' and hasSubTarget and 1 or 0;
    local index = tonumber(safe(0, function() return target:GetTargetIndex(slot); end)) or 0;
    if index <= 0 then
        return nil, nil, 'Select a monster first.';
    end
    return index, nil, nil;
end

local function currentTarget(token)
    local memory = safe(nil, function() return AshitaCore:GetMemoryManager(); end);
    if memory == nil then
        return nil, tx('error_runtime');
    end

    local entity = safe(nil, function() return memory:GetEntity(); end);
    if entity == nil then
        return nil, tx('error_runtime');
    end

    local index, nativeServerId, indexError = targetIndexForToken(memory, token);
    if index == nil then
        return nil, indexError;
    end

    local flags = tonumber(safe(0, function() return entity:GetSpawnFlags(index); end)) or 0;
    if bit.band(flags, 0x10) == 0 then
        return nil, tx('error_target_not_monster');
    end

    local name = tostring(safe('', function() return entity:GetName(index); end) or '');
    if name == '' then
        return nil, tx('error_target_name');
    end

    local serverId = tonumber(safe(nil, function() return entity:GetServerId(index); end));
    if not isPositiveInteger(serverId) then
        return nil, tx('error_target_id');
    end
    if isPositiveInteger(nativeServerId) and nativeServerId ~= serverId then
        return nil, tx('error_target_changed');
    end
    resolvedTargetIndexByServerId[serverId] = index;

    local party = safe(nil, function() return memory:GetParty(); end);
    local zone = party and tonumber(safe(nil, function() return party:GetMemberZone(0); end)) or nil;
    if not isPositiveInteger(zone) then
        return nil, tx('error_runtime');
    end

    return {
        index = index,
        serverId = serverId,
        name = name,
        zone = zone,
        token = token,
        memory = memory,
    }, nil;
end

local function targetMatches(expectedTarget, actualTarget)
    return expectedTarget ~= nil
        and actualTarget ~= nil
        and actualTarget.index == expectedTarget.index
        and actualTarget.serverId == expectedTarget.serverId
        and actualTarget.name == expectedTarget.name
        and actualTarget.zone == expectedTarget.zone
        and actualTarget.token == expectedTarget.token;
end

local function clockNow()
    return tonumber(safe(0, function() return os.clock(); end)) or 0;
end

local function castBarState(memory)
    local castBar = safe(nil, function() return memory:GetCastBar(); end);
    if castBar == nil then
        return nil, tx('error_runtime');
    end
    -- Count is the stable active-cast signal; Percent can be zero both at the
    -- start of a cast and while the cast bar is idle.
    local count = castBar and tonumber(safe(nil, function() return castBar:GetCount(); end)) or nil;
    if count == nil then
        return nil, tx('error_runtime');
    end
    return count > 0, nil, count;
end

local function currentDay()
    if vanaTimeAddress == nil or vanaTimeAddress <= 0 then
        local found = tonumber(safe(0, function()
            return ashita.memory.find('FFXiMain.dll', 0, VANA_TIME_SIGNATURE, 0, 0);
        end)) or 0;
        if found > 0 then
            vanaTimeAddress = found;
        end
    end
    if vanaTimeAddress == nil or vanaTimeAddress <= 0 then
        return nil, tx('error_runtime');
    end

    local pointer = tonumber(safe(0, function()
        return ashita.memory.read_uint32(vanaTimeAddress + 0x34);
    end)) or 0;
    if pointer <= 0 then
        return nil, tx('error_runtime');
    end

    local raw = tonumber(safe(nil, function()
        return ashita.memory.read_uint32(pointer + 0x0C);
    end));
    if raw == nil or raw <= 0 then
        return nil, tx('error_runtime');
    end

    local index = (math.floor((raw + VANA_TIME_EPOCH_OFFSET) / VANA_DAY_SECONDS) % 8) + 1;
    return dayElements[index], nil;
end

local function activeJobCanUse(resource, player)
    local requirements = resource and resource.LevelRequired;
    if requirements == nil then
        return false;
    end

    local jobs = {
        { id = tonumber(safe(0, function() return player:GetMainJob(); end)) or 0,
          level = tonumber(safe(0, function() return player:GetMainJobLevel(); end)) or 0 },
        { id = tonumber(safe(0, function() return player:GetSubJob(); end)) or 0,
          level = tonumber(safe(0, function() return player:GetSubJobLevel(); end)) or 0 },
    };

    for _, job in ipairs(jobs) do
        if job.id > 0 and job.level > 0 then
            local required = tonumber(safe(0, function() return requirements[job.id + 1]; end)) or 0;
            if required > 0 and required <= job.level then
                return true;
            end
        end
    end
    return false;
end

local function readySpells(memory, tierCeiling)
    local resources = safe(nil, function() return AshitaCore:GetResourceManager(); end);
    local player = safe(nil, function() return memory:GetPlayer(); end);
    local party = safe(nil, function() return memory:GetParty(); end);
    local recast = safe(nil, function() return memory:GetRecast(); end);
    if resources == nil or player == nil or party == nil or recast == nil then
        return nil, tx('error_runtime');
    end

    local mp = tonumber(safe(nil, function() return party:GetMemberMP(0); end));
    if mp == nil then
        return nil, tx('error_runtime');
    end

    local output = {};
    for _, spell in ipairs(spells) do
        local resource = safe(nil, function() return resources:GetSpellById(spell.id); end);
        local known = safe(false, function() return player:HasSpell(spell.id); end);
        local manaCost = resource and tonumber(resource.ManaCost) or nil;
        local timer = tonumber(safe(nil, function() return recast:GetSpellTimer(spell.id); end));
        local resourceName = resource and tostring(safe('', function() return resource.Name[1]; end) or '') or '';
        if resource ~= nil
            and resourceName == spell.name
            and (known == true or known == 1)
            and activeJobCanUse(resource, player)
            and manaCost ~= nil
            and manaCost <= mp
            and timer ~= nil
            and timer == 0
            and isPositiveInteger(spell.tier)
            and spell.tier <= tierCeiling
        then
            output[#output + 1] = spell;
        end
    end
    return output, nil;
end

local function cast(spell, expectedTarget)
    if expectedTarget.usesSetting == true then
        local configuredToken = configuredTargetToken();
        if configuredToken ~= expectedTarget.token then
            return false, tx('error_target_changed');
        end
    end

    local actualTarget, targetError = currentTarget(expectedTarget.token);
    if actualTarget == nil then
        return false, targetError;
    end
    if not targetMatches(expectedTarget, actualTarget) then
        return false, tx('error_target_changed');
    end

    local pending = pendingRequest;
    if pending == nil or not targetMatches(pending.target, expectedTarget) then
        return false, tx('error_runtime');
    end

    local commandTarget = expectedTarget.token;
    if resolvedTargetServerId(expectedTarget.token) ~= nil then
        local memory = safe(nil, function() return AshitaCore:GetMemoryManager(); end);
        local target = memory and safe(nil, function() return memory:GetTarget(); end) or nil;
        if target == nil then
            return false, tx('error_runtime');
        end
        local selected = pcall(function()
            target:SetTarget(expectedTarget.index, true);
        end);
        if not selected then
            return false, tx('error_target_select');
        end
        local selectedIndex = tonumber(safe(0, function() return target:GetTargetIndex(0); end)) or 0;
        local selectedServerId = tonumber(safe(0, function() return target:GetServerId(0); end)) or 0;
        if selectedIndex ~= expectedTarget.index or selectedServerId ~= expectedTarget.serverId then
            return false, tx('error_target_select');
        end
        commandTarget = '<t>';
    end

    local chatManager = safe(nil, function() return AshitaCore:GetChatManager(); end);
    if chatManager == nil then
        return false, tx('error_runtime');
    end

    -- Keep a prior submission recognizable until the instant this replacement
    -- is sent. A late category-8 acknowledgment can then still cancel the
    -- retry instead of allowing two casts from one pending request.
    pending.awaitingStart = false;
    pending.spellId = nil;
    pending.spellName = nil;
    pending.ackDeadline = nil;
    pending.sawCastBar = false;
    local ok = pcall(function()
        chatManager:QueueCommand(1, string.format('/ma "%s" %s', spell.name, commandTarget));
    end);
    if not ok then
        return false, tx('error_runtime');
    end

    local now = clockNow();
    pending.attempts = pending.attempts + 1;
    pending.awaitingStart = true;
    pending.spellId = spell.id;
    pending.spellName = spell.name;
    pending.ackDeadline = math.min(pending.expiresAt, now + START_ACK_SECONDS);
    pending.notBefore = math.max(pending.notBefore, pending.ackDeadline);
    pending.sawCastBar = false;
    return true, nil;
end

local function chooseDay(target)
    local day, dayError = currentDay();
    if day == nil then
        message(dayError, true);
        return false;
    end

    local tierCeiling, tierError = configuredTierCeiling('day');
    if tierCeiling == nil then
        message(tierError, true);
        return false;
    end

    local ready, readyError = readySpells(target.memory, tierCeiling);
    if ready == nil then
        message(readyError, true);
        return false;
    end

    local best = nil;
    local fallback = nil;
    for _, spell in ipairs(ready) do
        if spell.element == day.element then
            if spell.fallback then
                if fallback == nil or spell.tier > fallback.tier then
                    fallback = spell;
                end
            elseif best == nil or spell.power > best.power
                or (spell.power == best.power and spell.tier > best.tier)
            then
                best = spell;
            end
        end
    end
    best = best or fallback;
    if best == nil then
        message(tx('error_no_ready_day', day.element, day.day), true);
        return false;
    end

    local queued, queueError = cast(best, target);
    if not queued then
        message(queueError, true);
        return false;
    end
    routineMessage(tx('day_submitted', day.day, day.element, best.name));
    return true;
end

local function weaknessProfile(target)
    local index, indexError = loadWeaknessIndex();
    if index == nil then
        return nil, indexError;
    end
    local normalizedName = normalizeMobName(target.name);
    local profileId = index.names[normalizedName];
    if profileId == nil then
        local bestPrefixLength = 0;
        for prefix, familyProfileId in pairs(index.familyPrefixes) do
            local boundary = string.sub(normalizedName, #prefix + 1, #prefix + 1);
            if string.sub(normalizedName, 1, #prefix) == prefix
                and (boundary == '' or boundary == ' ' or boundary == '-' or boundary == "'")
                and #prefix > bestPrefixLength
            then
                profileId = familyProfileId;
                bestPrefixLength = #prefix;
            end
        end
    end
    if profileId == nil then
        -- Keep the validated index as the authority for recognized targets,
        -- but give custom mobs a neutral profile so the normal comparator
        -- chooses the strongest ready six-element tier-line spell.
        return { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 }, nil, true;
    end
    local profile = index.profiles[profileId];
    if not validProfile(profile) then
        return nil, tx('error_weakness_data');
    end
    return profile, nil, false;
end

local function chooseWeakness(target)
    local profile, profileError, usedFallback = weaknessProfile(target);
    if profile == nil then
        message(profileError, true);
        return false;
    end

    local tierCeiling, tierError = configuredTierCeiling('weak');
    if tierCeiling == nil then
        message(tierError, true);
        return false;
    end

    local ready, readyError = readySpells(target.memory, tierCeiling);
    if ready == nil then
        message(readyError, true);
        return false;
    end

    local bestByElement = {};
    for _, spell in ipairs(ready) do
        if spell.weak then
            local current = bestByElement[spell.element];
            if current == nil
                or spell.power > current.power
                or (spell.power == current.power and spell.tier > current.tier)
            then
                bestByElement[spell.element] = spell;
            end
        end
    end

    local candidates = {};
    for index, element in ipairs(weaknessElements) do
        local spell = bestByElement[element];
        if spell ~= nil then
            local multiplier = math.max(0, math.min(30000, 10000 + profile[index]));
            candidates[#candidates + 1] = {
                spell = spell,
                baseline = spell.power * multiplier,
                rank = profile[index + #weaknessElements],
            };
        end
    end
    if #candidates == 0 then
        message(tx('error_no_ready_weak'), true);
        return false;
    end

    local winner = nil;
    for _, candidate in ipairs(candidates) do
        if winner == nil
            or candidate.rank < winner.rank
            or (candidate.rank == winner.rank and candidate.baseline > winner.baseline)
            or (candidate.rank == winner.rank and candidate.baseline == winner.baseline
                and candidate.spell.power > winner.spell.power)
            or (candidate.rank == winner.rank and candidate.baseline == winner.baseline
                and candidate.spell.power == winner.spell.power
                and candidate.spell.id < winner.spell.id)
        then
            winner = candidate;
        end
    end

    local best = winner.spell;
    local queued, queueError = cast(best, target);
    if not queued then
        message(queueError, true);
        return false;
    end
    if usedFallback then
        routineMessage(tx('weak_unknown', target.name, best.name));
    else
        routineMessage(tx('weak_family', target.name, best.name));
    end
    return true;
end

local function executeAction(action, target)
    if action == 'weak' then
        return chooseWeakness(target);
    end
    return chooseDay(target);
end

local function cancelPendingRequest(reason)
    pendingRequest = nil;
    lastPresentAt = nil;
    if reason ~= nil then
        message(reason, true);
    end
end

local function processPendingRequest()
    if pendingRequest == nil then
        return;
    end

    local now = clockNow();
    if lastPresentAt ~= nil
        and now >= lastPresentAt
        and now - lastPresentAt < PRESENT_THROTTLE_SECONDS
    then
        return;
    end
    lastPresentAt = now;

    local pending = pendingRequest;
    if now >= pending.expiresAt then
        cancelPendingRequest(tx('error_runtime'));
        return;
    end

    if pending.target.usesSetting == true then
        local configuredToken = configuredTargetToken();
        if configuredToken ~= pending.target.token then
            cancelPendingRequest(tx('error_target_changed'));
            return;
        end
    end

    local actualTarget, targetError = currentTarget(pending.target.token);
    if actualTarget == nil then
        cancelPendingRequest(targetError);
        return;
    end
    actualTarget.usesSetting = pending.target.usesSetting == true;
    if not targetMatches(pending.target, actualTarget) then
        cancelPendingRequest(tx('error_target_changed'));
        return;
    end

    local busy, castBarError, castCount = castBarState(actualTarget.memory);
    if busy == nil then
        cancelPendingRequest(castBarError);
        return;
    end
    if pending.staleCastCount ~= nil then
        if busy and math.abs(castCount - pending.staleCastCount) < 0.001 then
            busy = false;
        else
            pending.staleCastCount = nil;
            if busy and not pending.awaitingStart then
                pending.castProbeCount = castCount;
                pending.castProbeUnchangedSince = now;
                pending.castProbeSawProgress = true;
                pending.notBefore = math.max(pending.notBefore, now + POST_CAST_LOCK_SECONDS);
                return;
            end
        end
    end
    if not pending.awaitingStart and pending.castProbeCount ~= nil then
        if not busy then
            pending.castProbeCount = nil;
            pending.castProbeUnchangedSince = nil;
            pending.castProbeSawProgress = nil;
            pending.notBefore = math.max(pending.notBefore, now + POST_CAST_LOCK_SECONDS);
        elseif math.abs(castCount - pending.castProbeCount) >= 0.001 then
            pending.castProbeCount = castCount;
            pending.castProbeUnchangedSince = now;
            pending.castProbeSawProgress = true;
            pending.notBefore = math.max(pending.notBefore, now + POST_CAST_LOCK_SECONDS);
            return;
        elseif now - pending.castProbeUnchangedSince < CAST_COUNT_STALE_SECONDS then
            return;
        else
            local sawProgress = pending.castProbeSawProgress == true;
            pending.castProbeCount = nil;
            pending.castProbeUnchangedSince = nil;
            pending.castProbeSawProgress = nil;
            pending.staleCastCount = castCount;
            if sawProgress then
                pending.notBefore = math.max(pending.notBefore, now + POST_CAST_LOCK_SECONDS);
            end
            busy = false;
            routineMessage(tx('cast_stale'));
        end
    end
    if busy then
        pending.notBefore = math.max(pending.notBefore, now + POST_CAST_LOCK_SECONDS);
        if pending.awaitingStart then
            pending.sawCastBar = true;
        end
        return;
    end

    if pending.awaitingStart then
        if pending.sawCastBar then
            cancelPendingRequest(tx('error_runtime'));
            return;
        end
        if pending.ackDeadline ~= nil then
            if now < pending.ackDeadline then
                return;
            end
            if pending.attempts >= MAX_SUBMISSIONS then
                cancelPendingRequest(tx('error_runtime'));
                return;
            end
            -- Retain awaitingStart and the prior spell identity throughout the
            -- retry lock so a slightly late action packet still prevents a
            -- duplicate. cast() clears it immediately before the next send.
            pending.ackDeadline = nil;
            pending.notBefore = math.max(pending.notBefore, now + RETRY_LOCK_SECONDS);
            routineMessage(tx('cast_retry'));
        end
    end
    if now < pending.notBefore then
        return;
    end

    local submitted = executeAction(pending.action, actualTarget);
    if not submitted and pendingRequest == pending then
        cancelPendingRequest(nil);
    end
end

local function requestAction(action, target)
    local busy, castBarError, castCount = castBarState(target.memory);
    if busy == nil then
        cancelPendingRequest(castBarError);
        return;
    end

    local now = clockNow();
    local previous = pendingRequest;
    local replaced = previous ~= nil;
    local inheritedNotBefore = previous and previous.notBefore or now;
    local inheritedAwaitingStart = previous and previous.awaitingStart or false;
    local inheritedSawCastBar = previous and previous.sawCastBar or false;
    local castProbeCount = previous and previous.castProbeCount or nil;
    local castProbeUnchangedSince = previous and previous.castProbeUnchangedSince or nil;
    local castProbeSawProgress = previous and previous.castProbeSawProgress or nil;
    local staleCastCount = previous and previous.staleCastCount or nil;
    if not inheritedAwaitingStart and busy and castProbeCount == nil and staleCastCount == nil then
        castProbeCount = castCount;
        castProbeUnchangedSince = now;
        castProbeSawProgress = false;
    end
    if inheritedAwaitingStart and busy then
        inheritedSawCastBar = true;
    end
    pendingRequest = {
        action = action,
        target = {
            index = target.index,
            serverId = target.serverId,
            name = target.name,
            zone = target.zone,
            token = target.token,
            usesSetting = target.usesSetting == true,
        },
        expiresAt = now + PENDING_REQUEST_TTL_SECONDS,
        notBefore = math.max(
            inheritedNotBefore,
            busy and castProbeCount == nil and (now + POST_CAST_LOCK_SECONDS) or now
        ),
        attempts = previous and previous.attempts or 0,
        awaitingStart = inheritedAwaitingStart,
        spellId = inheritedAwaitingStart and previous.spellId or nil,
        spellName = inheritedAwaitingStart and previous.spellName or nil,
        ackDeadline = inheritedAwaitingStart and previous.ackDeadline or nil,
        sawCastBar = inheritedSawCastBar,
        castProbeCount = castProbeCount,
        castProbeUnchangedSince = castProbeUnchangedSince,
        castProbeSawProgress = castProbeSawProgress,
        staleCastCount = staleCastCount,
    };
    lastPresentAt = nil;

    if busy
        or pendingRequest.castProbeCount ~= nil
        or now < pendingRequest.notBefore
        or pendingRequest.awaitingStart
    then
        local label = action == 'weak' and tx('weakness') or tx('day');
        local prefix = replaced and '> ' or '';
        routineMessage(tx('request_queued', prefix, label));
        return;
    end
    processPendingRequest();
end

local function confirmPendingCastStart(e)
    local pending = pendingRequest;
    if pending == nil or not pending.awaitingStart or e == nil or e.id ~= 0x028 then
        return;
    end

    local memory = safe(nil, function() return AshitaCore:GetMemoryManager(); end);
    local party = memory and safe(nil, function() return memory:GetParty(); end) or nil;
    local playerServerId = party and tonumber(safe(nil, function()
        return party:GetMemberServerId(0);
    end)) or nil;
    local actorServerId = tonumber(safe(nil, function()
        return struct.unpack('L', e.data, 0x05 + 1);
    end));
    if not isPositiveInteger(playerServerId) or actorServerId ~= playerServerId then
        return;
    end

    local category = tonumber(safe(nil, function()
        return ashita.bits.unpack_be(e.data_raw, 10, 2, 4);
    end));
    if category ~= 8 then
        return;
    end
    -- Category 8 identifies the spell in the first target action's 17-bit
    -- param field. The top-level param is a cast marker, not the spell ID.
    local spellId = tonumber(safe(nil, function()
        return ashita.bits.unpack_be(e.data_raw, 0, 213, 17);
    end));
    if spellId ~= pending.spellId then
        return;
    end

    local spellName = pending.spellName;
    cancelPendingRequest(nil);
    routineMessage(tx('cast_confirmed', spellName));
end

local function showHelp()
    message(tx('help_day'), false);
    message(tx('help_weak'), false);
    message(tx('help_optional'), false);
    message(tx('help_examples'), false);
    message(tx('help_settings'), false);
    message(tx('help_target'), false);
    message(tx('help_tier'), false);
    message(tx('help_chat'), false);
    message(tx('help_language'), false);
end

local function showTargetSetting()
    local token, tokenError = configuredTargetToken();
    if token == nil then
        message(tokenError, true);
        return;
    end
    message(tx('target_value', token), false);
end

local function tierAction(value)
    local action = string.lower(tostring(value or ''));
    if action == 'weakness' then
        return 'weak';
    end
    if action == 'day' or action == 'weak' then
        return action;
    end
    return nil;
end

local function showTierSetting(action)
    local ceiling, ceilingError = configuredTierCeiling(action);
    if ceiling == nil then
        message(ceilingError, true);
        return;
    end
    local label = action == 'day' and tx('day') or tx('weakness');
    message(tx('tier_value', label, tierRoman[ceiling], ceiling), false);
end

local function showTierSettings()
    showTierSetting('day');
    showTierSetting('weak');
end

local function showRoutineChatSetting()
    local enabled, settingError = configuredRoutineChat();
    if enabled == nil then
        message(settingError, true);
        return;
    end
    message(tx('chat_value', enabled and tx('on') or tx('off')), false);
end

local function showLanguageSetting()
    local language, settingError = configuredLanguage();
    if language == nil then
        message(settingError, true);
        return;
    end
    message(tx('language_value', localeNames[language]), false);
end

local function showSettings()
    showTargetSetting();
    showTierSettings();
    showRoutineChatSetting();
    showLanguageSetting();
end

local function requestConfiguredAction(action)
    local token, tokenError = requestTargetToken(nil);
    if token == nil then message(tokenError, true); return; end
    local target, targetError = currentTarget(token);
    if target == nil then message(targetError, true); return; end
    target.usesSetting = true;
    requestAction(action, target);
end

local function persistSettingsChanges(changes)
    if type(activeSettings) ~= 'table' then
        return false;
    end

    for _, change in ipairs(changes) do
        change.previous = activeSettings[change.key];
        activeSettings[change.key] = change.value;
    end

    local saveOk, saved = pcall(settings.save);
    if not saveOk or saved ~= true then
        for _, change in ipairs(changes) do
            activeSettings[change.key] = change.previous;
        end
        return false;
    end

    -- Ashita's public save wrapper does not expose a low-level file-open
    -- failure. Reload through the supported API and verify the value that was
    -- actually read back before reporting success.
    local reloadOk, reloaded = pcall(settings.reload);
    if not reloadOk or reloaded ~= true then
        for _, change in ipairs(changes) do
            activeSettings[change.key] = change.previous;
        end
        pcall(settings.save);
        return false;
    end

    local matched = type(activeSettings) == 'table';
    if matched then
        for _, change in ipairs(changes) do
            if activeSettings[change.key] ~= change.value then
                matched = false;
                break;
            end
        end
    end
    if matched then
        return true;
    end

    -- A mismatched reload is already the disk-backed state in the normal
    -- failure case. Restore only values that differ from the prior state, then
    -- make one best-effort reload so the cached table stays disk-backed.
    local needsRestore = false;
    if type(activeSettings) == 'table' then
        for _, change in ipairs(changes) do
            if activeSettings[change.key] ~= change.previous then
                activeSettings[change.key] = change.previous;
                needsRestore = true;
            end
        end
    end
    if needsRestore then
        pcall(settings.save);
        pcall(settings.reload);
    end
    return false;
end

local function setTargetToken(value)
    local token = string.lower(tostring(value or ''));
    if token ~= '<t>' and token ~= '<bt>' then
        message(tx('error_target_token'), true);
        return;
    end
    if not persistSettingsChanges({ { key='target', value=token } }) then
        message(tx('error_settings_save'), true);
        return;
    end
    message(tx('target_updated', token), false);
end

local function setTierCeiling(action, value)
    local ceiling = tierInputs[string.lower(tostring(value or ''))];
    if ceiling == nil then
        message(tx('error_tier'), true);
        return;
    end
    local key = action == 'day' and 'dayTierCeiling' or 'weaknessTierCeiling';
    if not persistSettingsChanges({ { key=key, value=ceiling } }) then
        message(tx('error_settings_save'), true);
        return;
    end
    local label = action == 'day' and tx('day') or tx('weakness');
    message(tx('tier_updated', label, tierRoman[ceiling], ceiling), false);
end

local function setRoutineChat(value)
    local enabled = nil;
    if type(value) == 'boolean' then
        enabled = value;
    else
        local token = string.lower(tostring(value or ''));
        if token == 'on' then
            enabled = true;
        elseif token == 'off' then
            enabled = false;
        end
    end
    if enabled == nil then
        message(tx('error_chat'), true);
        return;
    end
    if not persistSettingsChanges({ { key='showRoutineChat', value=enabled } }) then
        message(tx('error_settings_save'), true);
        return;
    end
    message(tx('chat_updated', enabled and tx('on') or tx('off')), false);
end

local function setLanguage(value)
    local language = string.lower(tostring(value or ''));
    if not isSupportedLanguage(language) then
        message(tx('error_language'), true);
        return;
    end
    if not persistSettingsChanges({ { key='language', value=language } }) then
        message(tx('error_settings_save'), true);
        return;
    end
    message(tx('language_updated', localeNames[language]), false);
end

local function resetSettings()
    if type(activeSettings) == 'table'
        and activeSettings.target == defaultSettings.target
        and activeSettings.dayTierCeiling == defaultSettings.dayTierCeiling
        and activeSettings.weaknessTierCeiling == defaultSettings.weaknessTierCeiling
        and activeSettings.showRoutineChat == defaultSettings.showRoutineChat
        and activeSettings.language == defaultSettings.language
        and activeSettings.onboardingComplete == defaultSettings.onboardingComplete
    then
        message(tx('settings_default'), false);
        return;
    end

    if not persistSettingsChanges({
        { key='target', value=defaultSettings.target },
        { key='dayTierCeiling', value=defaultSettings.dayTierCeiling },
        { key='weaknessTierCeiling', value=defaultSettings.weaknessTierCeiling },
        { key='showRoutineChat', value=defaultSettings.showRoutineChat },
        { key='language', value=defaultSettings.language },
        { key='onboardingComplete', value=defaultSettings.onboardingComplete },
    }) then
        message(tx('error_settings_reset'), true);
        return;
    end
    message(tx('settings_reset'), false);
end

local function renderTierCombo(label, action)
    local current = configuredTierCeiling(action);
    local preview = current and string.format('%s (%d)', tierRoman[current], current)
        or tx('error_tier');
    local comboOpen = false;
    local renderOk, renderError = pcall(function()
        comboOpen = imgui.BeginCombo(label, preview);
        if not comboOpen then
            return;
        end
        for tier = 1, 5 do
            local visibleLabel = string.format('%s (%d)', tierRoman[tier], tier);
            local itemLabel = string.format('%s##oddcast_%s_%d', visibleLabel, action, tier);
            if imgui.Selectable(itemLabel, current == tier) and current ~= tier then
                setTierCeiling(action, tostring(tier));
            end
        end
    end);
    if comboOpen then
        local closeOk, closeError = pcall(imgui.EndCombo);
        if renderOk and not closeOk then
            renderOk = false;
            renderError = closeError;
        end
    end
    if not renderOk then
        error(renderError);
    end
end

local function renderLanguageCombo()
    local current = configuredLanguage();
    local preview = current and localeNames[current] or tx('error_language');
    local comboOpen = false;
    local renderOk, renderError = pcall(function()
        comboOpen = imgui.BeginCombo(tx('language'), preview);
        if not comboOpen then
            return;
        end
        for _, code in ipairs(localeOrder) do
            local itemLabel = string.format('%s##oddcast_language_%s', localeNames[code], code);
            if imgui.Selectable(itemLabel, current == code) and current ~= code then
                setLanguage(code);
            end
        end
    end);
    if comboOpen then
        local closeOk, closeError = pcall(imgui.EndCombo);
        if renderOk and not closeOk then
            renderOk = false;
            renderError = closeError;
        end
    end
    if not renderOk then
        error(renderError);
    end
end

local function renderSettingsWindow()
    if settingsWindowOpen[1] ~= true then
        return;
    end

    local beginCalled = false;
    local pushed = nil;
    local localeFontPushed = false;
    local renderOk, renderError = pcall(function()
        local language = currentLanguage();
        localeFontPushed = uiSkin.push_locale_font ~= nil
            and uiSkin.push_locale_font(imgui, localeFonts, language) == true;
        guiLocaleActive = language ~= 'ja' and language ~= 'zh' or localeFontPushed;
        imgui.SetNextWindowSize({ 560, 610 }, ImGuiCond_FirstUseEver);
        pushed = uiSkin.push_window(imgui);
        local visible = imgui.Begin(
            tx('control_title'),
            settingsWindowOpen,
            ImGuiWindowFlags_AlwaysVerticalScrollbar
        );
        beginCalled = true;
        if not visible then
            return;
        end

        if activeSettings.onboardingComplete ~= true then
            uiSkin.section_header(imgui, tx('welcome_title'));
            imgui.TextWrapped(tx('welcome_body'));
            if uiSkin.button(imgui, tx('finish_setup'), true, { 180, 0 }) then
                if persistSettingsChanges({ { key='onboardingComplete', value=true } }) then
                    message(tx('setup_complete'), false);
                else
                    message(tx('error_settings_save'), true);
                end
            end
            imgui.Spacing();
        end

        uiSkin.section_header(imgui, tx('cast_section'));
        imgui.TextWrapped(tx('cast_explain'));
        if uiSkin.button(imgui, tx('cast_day'), true, { 245, 34 }) then requestConfiguredAction('day'); end
        imgui.SameLine();
        if uiSkin.button(imgui, tx('cast_weak'), true, { 245, 34 }) then requestConfiguredAction('weak'); end
        local pendingText = pendingRequest == nil and tx('queue_idle')
            or tx('queue_pending', pendingRequest.action == 'day' and tx('day') or tx('weakness'), pendingRequest.target.name);
        uiSkin.muted(imgui, pendingText);

        uiSkin.section_header(imgui, tx('target'));
        local target = configuredTargetToken();
        if target == nil then
            imgui.TextWrapped(tx('target_invalid'));
        end
        if imgui.RadioButton(tx('target_current'), target == '<t>') and target ~= '<t>' then
            setTargetToken('<t>');
        end
        if imgui.RadioButton(tx('target_battle'), target == '<bt>') and target ~= '<bt>' then
            setTargetToken('<bt>');
        end

        uiSkin.section_header(imgui, tx('tier_section'));
        renderTierCombo(tx('day'), 'day');
        renderTierCombo(tx('weakness'), 'weak');
        imgui.TextWrapped(tx('tier_explain'));

        uiSkin.section_header(imgui, tx('chat_section'));
        local routineChat = configuredRoutineChat();
        if routineChat == nil then
            imgui.TextWrapped(tx('chat_invalid'));
        end
        local routineChatRef = { routineChat == true };
        if imgui.Checkbox(tx('chat_show'), routineChatRef) then
            setRoutineChat(routineChatRef[1]);
        end
        imgui.TextWrapped(tx('chat_explain'));

        uiSkin.section_header(imgui, tx('language_section'));
        local language = configuredLanguage();
        if language == nil then
            imgui.TextWrapped(tx('language_invalid'));
        end
        renderLanguageCombo();
        imgui.TextWrapped(tx('language_explain'));

        uiSkin.section_header(imgui, tx('update_section'));
        imgui.Text(tx('installed_version', addon.version));
        if updateState.status == 'available' then
            imgui.TextWrapped(tx('update_available', updateState.latest_version));
            uiSkin.muted(imgui, updateState.release_url);
            if uiSkin.button(imgui, tx('install_update'), true, { 245, 34 }) then
                beginUpdateInstall();
            end
        elseif updateState.status == 'installing' or updateState.status == 'reloading' then
            imgui.TextWrapped(tx('update_installing'));
        elseif updateState.status == 'install_error' then
            imgui.TextWrapped(tx('update_failed', updateState.detail or 'unknown error'));
        elseif updateState.status == 'current' then
            imgui.Text(tx('update_current'));
        elseif updateState.status == 'unavailable' or updateState.status == 'invalid' then
            imgui.TextWrapped(tx('update_unavailable'));
        end
        if uiSkin.button(imgui, tx('check_updates'), false) then
            updateState = updateChecker.check(addon.version);
        end
        imgui.SameLine();
        if imgui.Button(tx('reset')) then
            resetSettings();
        end
    end);

    local closeOk = true;
    if beginCalled then
        closeOk = pcall(imgui.End);
    end
    if pushed ~= nil then pcall(uiSkin.pop, imgui, pushed); end
    guiLocaleActive = false;
    if localeFontPushed and uiSkin.pop_locale_font ~= nil then
        pcall(uiSkin.pop_locale_font, imgui);
    end
    if not renderOk or not closeOk then
        settingsWindowOpen[1] = false;
        message(tx('error_render'), true);
        return;
    end
end

ashita.events.register('command', 'oddcast_command_cb', function(e)
    local args = e.command:args();
    local prefix = string.lower(tostring(args[1] or ''));
    if prefix ~= '/oddcast' and prefix ~= '/oc' then
        return;
    end
    e.blocked = true;

    local action = string.lower(tostring(args[2] or 'help'));
    if action == 'target' then
        if args[4] ~= nil then
            message(tx('error_usage'), true);
            return;
        end
        if args[3] == nil then
            showTargetSetting();
        else
            setTargetToken(args[3]);
        end
        return;
    end
    if action == 'tier' then
        if args[5] ~= nil then
            message(tx('error_usage'), true);
            return;
        end
        if args[3] == nil then
            showTierSettings();
            return;
        end
        local tierMode = tierAction(args[3]);
        if tierMode == nil then
            message(tx('error_usage'), true);
            return;
        end
        if args[4] == nil then
            showTierSetting(tierMode);
        else
            setTierCeiling(tierMode, args[4]);
        end
        return;
    end
    if action == 'chat' then
        if args[4] ~= nil then
            message(tx('error_usage'), true);
            return;
        end
        if args[3] == nil then
            showRoutineChatSetting();
        else
            setRoutineChat(args[3]);
        end
        return;
    end
    if action == 'language' or action == 'lang' then
        if args[4] ~= nil then
            message(tx('error_usage'), true);
            return;
        end
        if args[3] == nil then
            showLanguageSetting();
        else
            setLanguage(args[3]);
        end
        return;
    end
    if action == 'help' or action == '?' then
        if args[3] ~= nil then
            message(tx('error_usage'), true);
            return;
        end
        showHelp();
        return;
    end
    if action == 'settings' then
        if args[3] ~= nil then
            message(tx('error_usage'), true);
            return;
        end
        settingsWindowOpen[1] = true;
        showSettings();
        return;
    end
    if action ~= 'day' and action ~= 'weak' and action ~= 'weakness' then
        message(tx('error_unknown'), true);
        return;
    end

    if args[4] ~= nil then
        message(tx('error_usage'), true);
        return;
    end

    local usesSetting = args[3] == nil;
    local token, tokenError = requestTargetToken(args[3]);
    if token == nil then
        message(tokenError, true);
        return;
    end
    local target, targetError = currentTarget(token);
    if target == nil then
        message(targetError, true);
        return;
    end
    if token == '[t]' then
        target.token = tostring(target.serverId);
    end
    target.usesSetting = usesSetting;
    requestAction(action == 'day' and 'day' or 'weak', target);
end);

ashita.events.register('packet_in', 'oddcast_cast_start_cb', function(e)
    confirmPendingCastStart(e);
end);

ashita.events.register('d3d_present', 'oddcast_pending_cast_cb', function()
    processPendingRequest();
    processUpdateInstall();
    renderSettingsWindow();
end);

ashita.events.register('unload', 'oddcast_unload_cb', function()
    settingsWindowOpen[1] = false;
    cancelPendingRequest(nil);
end);

ashita.events.register('load', 'oddcast_load_cb', function()
    routineMessage(tx('loaded'));
    if activeSettings == nil or activeSettings.onboardingComplete ~= true then
        settingsWindowOpen[1] = true;
    end
end);
