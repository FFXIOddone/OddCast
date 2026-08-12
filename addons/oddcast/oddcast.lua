addon.name = 'oddcast';
addon.author = 'OddLua';
addon.version = '0.1.1';
addon.desc = 'Selects a ready nuke for the current Vana day and fails closed on unvalidated weakness data.';

require('common');
local bit = require('bit');
local chat = require('chat');

local VANA_TIME_SIGNATURE = 'B0015EC390518B4C24088D4424005068';
local VANA_TIME_EPOCH_OFFSET = 92514960;
local VANA_DAY_SECONDS = 3456;

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

local function currentTarget()
    local memory = safe(nil, function() return AshitaCore:GetMemoryManager(); end);
    if memory == nil then
        return nil, 'Ashita memory is unavailable.';
    end

    local target = safe(nil, function() return memory:GetTarget(); end);
    local entity = safe(nil, function() return memory:GetEntity(); end);
    if target == nil or entity == nil then
        return nil, 'Target memory is unavailable.';
    end

    -- OddCast queues <t>, so validate the main target that <t> will resolve to.
    local index = tonumber(safe(0, function() return target:GetTargetIndex(0); end)) or 0;
    if index <= 0 then
        return nil, 'Select a monster first.';
    end

    local flags = tonumber(safe(0, function() return entity:GetSpawnFlags(index); end)) or 0;
    if bit.band(flags, 0x10) == 0 then
        return nil, 'The selected target is not a monster.';
    end

    local name = tostring(safe('', function() return entity:GetName(index); end) or '');
    if name == '' then
        return nil, 'The selected monster has no readable name.';
    end

    return { index = index, name = name, memory = memory }, nil;
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

local function cast(spell, expectedTarget, expectedZone)
    local actualTarget = currentTarget();
    if actualTarget == nil
        or actualTarget.index ~= expectedTarget.index
        or actualTarget.name ~= expectedTarget.name
    then
        return false, 'Target changed during selection; no spell was queued.';
    end
    if expectedZone ~= nil then
        local party = safe(nil, function() return actualTarget.memory:GetParty(); end);
        local actualZone = party and tonumber(safe(nil, function() return party:GetMemberZone(0); end)) or nil;
        if actualZone ~= expectedZone then
            return false, 'Zone changed during selection; no spell was queued.';
        end
    end

    local chatManager = safe(nil, function() return AshitaCore:GetChatManager(); end);
    if chatManager == nil then
        return false, 'Ashita chat manager is unavailable; no spell was queued.';
    end
    local ok = pcall(function()
        chatManager:QueueCommand(1, string.format('/ma "%s" <t>', spell.name));
    end);
    if not ok then
        return false, 'Ashita rejected the queued spell command.';
    end
    return true, nil;
end

local function chooseDay(target)
    local day, dayError = currentDay();
    if day == nil then
        message(dayError, true);
        return;
    end

    local ready, readyError = readySpells(target.memory);
    if ready == nil then
        message(readyError, true);
        return;
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
        return;
    end

    local queued, queueError = cast(best, target, nil);
    if not queued then
        message(queueError, true);
        return;
    end
    message(string.format('%s (%s): queued %s.', day.day, day.element, best.name), false);
end

local function chooseWeakness()
    message(
        'Weakness selection is disabled: legacy MobDB modifiers are not validated against current CatsEye resistance data; no spell was queued.',
        true
    );
end

local function showHelp()
    message('/oddcast day | /oc day - highest modeled ready spell matching the current Vana day.', false);
    message('/oddcast weakness | /oc weak - disabled until exact CatsEye target resistance data is validated.', false);
end

ashita.events.register('command', 'oddcast_command_cb', function(e)
    local args = e.command:args();
    local prefix = string.lower(tostring(args[1] or ''));
    if prefix ~= '/oddcast' and prefix ~= '/oc' then
        return;
    end
    e.blocked = true;

    local action = string.lower(tostring(args[2] or 'help'));
    if args[3] ~= nil then
        message('Too many arguments. Use /oc help.', true);
        return;
    end
    if action == 'help' or action == '?' then
        showHelp();
        return;
    end
    if action ~= 'day' and action ~= 'weak' and action ~= 'weakness' then
        message('Unknown command. Use /oc help.', true);
        return;
    end

    if action == 'weak' or action == 'weakness' then
        chooseWeakness();
        return;
    end

    local target, targetError = currentTarget();
    if target == nil then
        message(targetError, true);
        return;
    end
    chooseDay(target);
end);

ashita.events.register('load', 'oddcast_load_cb', function()
    message('Loaded. Use /oc day, /oc weak, or /oc help.', false);
end);
