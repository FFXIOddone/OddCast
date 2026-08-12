-- SPDX-License-Identifier: GPL-3.0-or-later
-- Copyright (c) 2026 Oddone
-- Modified for OddCast on 2026-08-12; see THIRD_PARTY_NOTICES.md.

addon.name = 'oddcast';
addon.author = 'Oddone';
addon.version = '0.2.4';
addon.desc = 'Selects a ready nuke for the current Vana day or a typical mob-family weakness.';

require('common');
local bit = require('bit');
local chat = require('chat');
local ffi = require('ffi');
local settings = require('settings');

local defaultSettings = T{
    target = '<t>',
};
local activeSettings = settings.load(defaultSettings);
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
local START_ACK_SECONDS = 2.0;
local RETRY_LOCK_SECONDS = 1.1;
local MAX_SUBMISSIONS = 4;
local PRESENT_THROTTLE_SECONDS = 0.05;
local pendingRequest = nil;
local lastPresentAt = nil;

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
    -- Light/dark spells remain available to the day command, but they use
    -- different stat/formula families and are not compared with INT tier nukes.
    { id=28,  name='Banish',     element='Light',     tier=1, power=14,  weak=false },
    { id=29,  name='Banish II',  element='Light',     tier=2, power=85,  weak=false },
    { id=30,  name='Banish III', element='Light',     tier=3, power=198, weak=false },
    { id=21,  name='Holy',       element='Light',     tier=1, power=125, weak=false },
    { id=22,  name='Holy II',    element='Light',     tier=2, power=250, weak=false },
    { id=219, name='Comet',      element='Dark',      tier=1, power=700, weak=false },
    { id=245, name='Drain',      element='Dark',      tier=1, power=0,   weak=false, fallback=true },
    { id=246, name='Drain II',   element='Dark',      tier=2, power=0,   weak=false, fallback=true },
    { id=880, name='Drain III',  element='Dark',      tier=3, power=0,   weak=false, fallback=true },
};

local vanaTimeAddress = nil;
local battleTargetAddress = nil;

local weaknessElements = { 'Fire', 'Ice', 'Wind', 'Earth', 'Lightning', 'Water' };

local function safe(defaultValue, callback)
    local ok, value = pcall(callback);
    if ok and value ~= nil then
        return value;
    end
    return defaultValue;
end

local function message(text, isError)
    local formatter = isError and chat.error or chat.message;
    print(chat.header('OddCast') .. formatter(text));
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
        return nil, 'OddCast addon path is unavailable; no spell was queued.';
    end
    local ok, data = pcall(dofile, path);
    if not ok or type(data) ~= 'table' then
        return nil, 'Weakness index is missing or unreadable; no spell was queued.';
    end
    if data.schema ~= WEAKNESS_SCHEMA
        or not isSha256(data.sourceSha256)
        or type(data.elements) ~= 'table'
        or type(data.profiles) ~= 'table'
        or type(data.names) ~= 'table'
        or type(data.familyPrefixes) ~= 'table'
    then
        return nil, 'Weakness index is malformed; no spell was queued.';
    end
    local elementCount = 0;
    for key in pairs(data.elements) do
        elementCount = elementCount + 1;
        if not isPositiveInteger(key) or key > #weaknessElements then
            return nil, 'Weakness index element list is invalid; no spell was queued.';
        end
    end
    for index, element in ipairs(weaknessElements) do
        if data.elements[index] ~= element then
            return nil, 'Weakness index element order is invalid; no spell was queued.';
        end
    end
    if elementCount ~= #weaknessElements then
        return nil, 'Weakness index element list is invalid; no spell was queued.';
    end
    for profileId, profile in pairs(data.profiles) do
        if not isNonNegativeInteger(profileId) or not validProfile(profile) then
            return nil, 'Weakness index contains a malformed resistance profile; no spell was queued.';
        end
    end
    for name, profileId in pairs(data.names) do
        if type(name) ~= 'string' or name == '' or normalizeMobName(name) ~= name
            or not isNonNegativeInteger(profileId) or data.profiles[profileId] == nil
        then
            return nil, 'Weakness index contains a malformed mob-name mapping; no spell was queued.';
        end
    end
    for prefix, profileId in pairs(data.familyPrefixes) do
        if type(prefix) ~= 'string' or prefix == '' or normalizeMobName(prefix) ~= prefix
            or not isNonNegativeInteger(profileId) or data.profiles[profileId] == nil
        then
            return nil, 'Weakness index contains a malformed family mapping; no spell was queued.';
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
    return nil, 'OddCast target setting is invalid. Use /oc target <t> or /oc target <bt>.';
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
        return nil, nil, 'The <bt> resolver is unavailable; no spell was queued.';
    end

    local ok, actor = pcall(function()
        local seekBattleActor = ffi.cast('OddCastSeekBattleActor_f', battleTargetAddress);
        return seekBattleActor();
    end);
    if not ok then
        battleTargetAddress = nil;
        return nil, nil, 'The <bt> resolver failed; no spell was queued.';
    end
    if actor == nil then
        return nil, nil, 'No battle target is available for <bt>.';
    end

    local index = tonumber(safe(nil, function() return actor.id.GuideNo; end));
    local serverId = tonumber(safe(nil, function() return actor.id.UniqueNo; end));
    if not isPositiveInteger(index) then
        return nil, nil, 'No battle target is available for <bt>.';
    end
    return index, serverId, nil;
end

local function targetIndexForToken(memory, token)
    if token == '<bt>' then
        return battleTargetIndex();
    end

    local target = safe(nil, function() return memory:GetTarget(); end);
    if target == nil then
        return nil, nil, 'Target memory is unavailable.';
    end
    local subTargetActive = safe(nil, function() return target:GetIsSubTargetActive(); end);
    if subTargetActive == nil then
        return nil, nil, 'The <t> target state is unavailable; no spell was queued.';
    end
    if subTargetActive == true or (tonumber(subTargetActive) or 0) ~= 0 then
        return nil, nil, 'Finish or cancel the active subtarget before using OddCast.';
    end

    local index = tonumber(safe(0, function() return target:GetTargetIndex(0); end)) or 0;
    if index <= 0 then
        return nil, nil, 'Select a monster first.';
    end
    return index, nil, nil;
end

local function currentTarget(token)
    local memory = safe(nil, function() return AshitaCore:GetMemoryManager(); end);
    if memory == nil then
        return nil, 'Ashita memory is unavailable.';
    end

    local entity = safe(nil, function() return memory:GetEntity(); end);
    if entity == nil then
        return nil, 'Entity memory is unavailable.';
    end

    local index, nativeServerId, indexError = targetIndexForToken(memory, token);
    if index == nil then
        return nil, indexError;
    end

    local flags = tonumber(safe(0, function() return entity:GetSpawnFlags(index); end)) or 0;
    if bit.band(flags, 0x10) == 0 then
        return nil, 'The selected target is not a monster.';
    end

    local name = tostring(safe('', function() return entity:GetName(index); end) or '');
    if name == '' then
        return nil, 'The selected monster has no readable name.';
    end

    local serverId = tonumber(safe(nil, function() return entity:GetServerId(index); end));
    if not isPositiveInteger(serverId) then
        return nil, 'The selected monster has no readable server ID.';
    end
    if isPositiveInteger(nativeServerId) and nativeServerId ~= serverId then
        return nil, 'The <bt> identity changed during resolution; no spell was queued.';
    end

    local party = safe(nil, function() return memory:GetParty(); end);
    local zone = party and tonumber(safe(nil, function() return party:GetMemberZone(0); end)) or nil;
    if not isPositiveInteger(zone) then
        return nil, 'The current zone is unavailable.';
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
        return nil, 'Ashita cast-bar state is unavailable; no spell was queued.';
    end
    -- Count is the stable active-cast signal; Percent can be zero both at the
    -- start of a cast and while the cast bar is idle.
    local count = castBar and tonumber(safe(nil, function() return castBar:GetCount(); end)) or nil;
    if count == nil then
        return nil, 'Ashita cast-bar state is unavailable; no spell was queued.';
    end
    return count > 0, nil;
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
        return nil, 'Vana time signature scan failed; no spell was queued.';
    end

    local pointer = tonumber(safe(0, function()
        return ashita.memory.read_uint32(vanaTimeAddress + 0x34);
    end)) or 0;
    if pointer <= 0 then
        return nil, 'Vana time pointer is unavailable; no spell was queued.';
    end

    local raw = tonumber(safe(nil, function()
        return ashita.memory.read_uint32(pointer + 0x0C);
    end));
    if raw == nil or raw <= 0 then
        return nil, 'Vana time value is unavailable; no spell was queued.';
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

local function readySpells(memory)
    local resources = safe(nil, function() return AshitaCore:GetResourceManager(); end);
    local player = safe(nil, function() return memory:GetPlayer(); end);
    local party = safe(nil, function() return memory:GetParty(); end);
    local recast = safe(nil, function() return memory:GetRecast(); end);
    if resources == nil or player == nil or party == nil or recast == nil then
        return nil, 'Spell, player, party, or recast data is unavailable.';
    end

    local mp = tonumber(safe(nil, function() return party:GetMemberMP(0); end));
    if mp == nil then
        return nil, 'Current MP is unavailable.';
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
        then
            output[#output + 1] = spell;
        end
    end
    return output, nil;
end

local function cast(spell, expectedTarget)
    local configuredToken = configuredTargetToken();
    if configuredToken ~= expectedTarget.token then
        return false, 'Target setting changed during selection; no spell was queued.';
    end

    local actualTarget, targetError = currentTarget(expectedTarget.token);
    if actualTarget == nil then
        return false, targetError;
    end
    if not targetMatches(expectedTarget, actualTarget) then
        return false, 'Target changed during selection; no spell was queued.';
    end

    local pending = pendingRequest;
    if pending == nil or not targetMatches(pending.target, expectedTarget) then
        return false, 'Pending spell identity changed before submission; no retry was armed.';
    end

    local chatManager = safe(nil, function() return AshitaCore:GetChatManager(); end);
    if chatManager == nil then
        return false, 'Ashita chat manager is unavailable; no spell was queued.';
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
        chatManager:QueueCommand(1, string.format('/ma "%s" %s', spell.name, expectedTarget.token));
    end);
    if not ok then
        return false, 'Ashita rejected the queued spell command.';
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

    local ready, readyError = readySpells(target.memory);
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
        message(string.format('No ready %s spell is learned for %s.', day.element, day.day), true);
        return false;
    end

    local queued, queueError = cast(best, target);
    if not queued then
        message(queueError, true);
        return false;
    end
    message(string.format('%s (%s): submitted %s.', day.day, day.element, best.name), false);
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
        return nil, 'No typical mob-family weakness matches this target; no spell was queued.';
    end
    local profile = index.profiles[profileId];
    if not validProfile(profile) then
        return nil, 'The target weakness profile is malformed; no spell was queued.';
    end
    return profile, nil;
end

local function chooseWeakness(target)
    local profile, profileError = weaknessProfile(target);
    if profile == nil then
        message(profileError, true);
        return false;
    end

    local ready, readyError = readySpells(target.memory);
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
        message('No ready six-element tier-line spell is available; no spell was queued.', true);
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
    message(string.format('%s: typical family baseline submitted %s.', target.name, best.name), false);
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
        cancelPendingRequest('Pending spell request expired; no spell was submitted.');
        return;
    end

    local configuredToken = configuredTargetToken();
    if configuredToken ~= pending.target.token then
        cancelPendingRequest('Target setting changed while the spell request was pending; no spell was submitted.');
        return;
    end

    local actualTarget, targetError = currentTarget(pending.target.token);
    if actualTarget == nil then
        cancelPendingRequest(targetError);
        return;
    end
    if not targetMatches(pending.target, actualTarget) then
        cancelPendingRequest('Target changed while the spell request was pending; no spell was submitted.');
        return;
    end

    local busy, castBarError = castBarState(actualTarget.memory);
    if busy == nil then
        cancelPendingRequest(castBarError);
        return;
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
            cancelPendingRequest('A cast began without a matching OddCast spell confirmation; the pending request was canceled.');
            return;
        end
        if pending.ackDeadline ~= nil then
            if now < pending.ackDeadline then
                return;
            end
            if pending.attempts >= MAX_SUBMISSIONS then
                cancelPendingRequest('The client did not start the queued spell after four bounded submissions.');
                return;
            end
            -- Retain awaitingStart and the prior spell identity throughout the
            -- retry lock so a slightly late action packet still prevents a
            -- duplicate. cast() clears it immediately before the next send.
            pending.ackDeadline = nil;
            pending.notBefore = math.max(pending.notBefore, now + RETRY_LOCK_SECONDS);
            message('No spell start was confirmed; the pending request will retry.', true);
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
    local busy, castBarError = castBarState(target.memory);
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
        },
        expiresAt = now + PENDING_REQUEST_TTL_SECONDS,
        notBefore = math.max(inheritedNotBefore, busy and (now + POST_CAST_LOCK_SECONDS) or now),
        attempts = previous and previous.attempts or 0,
        awaitingStart = inheritedAwaitingStart,
        spellId = inheritedAwaitingStart and previous.spellId or nil,
        spellName = inheritedAwaitingStart and previous.spellName or nil,
        ackDeadline = inheritedAwaitingStart and previous.ackDeadline or nil,
        sawCastBar = inheritedSawCastBar,
    };
    lastPresentAt = nil;

    if busy or now < pendingRequest.notBefore or pendingRequest.awaitingStart then
        local label = action == 'weak' and 'Weakness' or 'Day';
        local prefix = replaced and 'Replaced the pending request. ' or '';
        message(string.format('%s%s request queued; waiting for the current submission or action lock.', prefix, label), false);
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
    -- Category 8 stores the spell command argument in the top-level 16-bit Param field.
    local spellId = tonumber(safe(nil, function()
        return ashita.bits.unpack_be(e.data_raw, 10, 6, 16);
    end));
    if spellId ~= pending.spellId then
        return;
    end

    local spellName = pending.spellName;
    cancelPendingRequest(nil);
    message(string.format('Confirmed cast start: %s.', spellName), false);
end

local function showHelp()
    message('/oddcast day | /oc day - highest modeled ready spell matching the current Vana day.', false);
    message('/oddcast weakness | /oc weak - typical mob-family weakness, independent of zone.', false);
    message('/oddcast settings | /oc settings - show current text settings.', false);
    message('/oddcast target [<t>|<bt>] | /oc target [<t>|<bt>] - show or set the hostile target token.', false);
end

local function showSettings()
    local token, tokenError = configuredTargetToken();
    if token == nil then
        message(tokenError, true);
        return;
    end
    message(string.format('Target token: %s', token), false);
end

local function setTargetToken(value)
    local token = string.lower(tostring(value or ''));
    if token ~= '<t>' and token ~= '<bt>' then
        message('Unsupported target token. Use /oc target <t> or /oc target <bt>.', true);
        return;
    end
    if type(activeSettings) ~= 'table' then
        message('OddCast settings are unavailable; target was not changed.', true);
        return;
    end

    local previous = activeSettings.target;
    activeSettings.target = token;
    local ok, saved = pcall(settings.save);
    if not ok or saved ~= true then
        activeSettings.target = previous;
        message('Ashita could not save the OddCast target setting.', true);
        return;
    end
    message(string.format('Target token set: %s', token), false);
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
            message('Too many arguments. Use /oc target <t> or /oc target <bt>.', true);
            return;
        end
        if args[3] == nil then
            showSettings();
        else
            setTargetToken(args[3]);
        end
        return;
    end
    if args[3] ~= nil then
        message('Too many arguments. Use /oc help.', true);
        return;
    end
    if action == 'help' or action == '?' then
        showHelp();
        return;
    end
    if action == 'settings' then
        showSettings();
        return;
    end
    if action ~= 'day' and action ~= 'weak' and action ~= 'weakness' then
        message('Unknown command. Use /oc help.', true);
        return;
    end

    local token, tokenError = configuredTargetToken();
    if token == nil then
        message(tokenError, true);
        return;
    end
    if action == 'weak' or action == 'weakness' then
        local target, targetError = currentTarget(token);
        if target == nil then
            message(targetError, true);
            return;
        end
        requestAction('weak', target);
    else
        local target, targetError = currentTarget(token);
        if target == nil then
            message(targetError, true);
            return;
        end
        requestAction('day', target);
    end
end);

ashita.events.register('packet_in', 'oddcast_cast_start_cb', function(e)
    confirmPendingCastStart(e);
end);

ashita.events.register('d3d_present', 'oddcast_pending_cast_cb', function()
    processPendingRequest();
end);

ashita.events.register('unload', 'oddcast_unload_cb', function()
    cancelPendingRequest(nil);
end);

ashita.events.register('load', 'oddcast_load_cb', function()
    message('Loaded. Use /oc day, /oc weak, /oc settings, or /oc help.', false);
end);
