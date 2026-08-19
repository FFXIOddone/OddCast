-- SPDX-License-Identifier: GPL-3.0-or-later
local checker = {}
local API_URL = 'https://api.github.com/repos/FFXIOddone/OddCast/releases/latest'
local RELEASE_URL = 'https://github.com/FFXIOddone/OddCast/releases/latest'

local function version(value)
    local major, minor, patch = tostring(value or ''):gsub('^OddCast%-v', ''):gsub('^v', ''):match('^(%d+)%.(%d+)%.(%d+)$')
    if major == nil then return nil end
    return { tonumber(major), tonumber(minor), tonumber(patch) }
end

local function newer(candidate, current)
    for index = 1, 3 do
        if candidate[index] ~= current[index] then return candidate[index] > current[index] end
    end
    return false
end

local function request()
    local httpsOk, https = pcall(require, 'socket.ssl.https')
    local ltn12Ok, ltn12 = pcall(require, 'socket.ltn12')
    if not httpsOk or not ltn12Ok then return nil, nil end
    local chunks = {}
    local previousTimeout = https.TIMEOUT
    https.TIMEOUT = 4
    -- ODD_NETWORK_CALL: manual read-only GET to OddCast's fixed public release endpoint.
    local called, ok, code = pcall(https.request, {
        url=API_URL, method='GET',
        headers={ ['Accept']='application/vnd.github+json', ['User-Agent']='OddCast-update-checker' },
        sink=ltn12.sink.table(chunks),
    })
    https.TIMEOUT = previousTimeout
    if not called or not ok then return nil, nil end
    return table.concat(chunks), tonumber(code)
end

function checker.check(currentVersion, dependencies)
    dependencies = dependencies or {}
    local body, status = (dependencies.request or request)()
    if body == nil or status ~= 200 then return { status='unavailable', release_url=RELEASE_URL } end
    local tag = tostring(body):match('"tag_name"%s*:%s*"([^"]+)"')
    local current, latest = version(currentVersion), version(tag)
    if current == nil or latest == nil then return { status='invalid', release_url=RELEASE_URL } end
    local latestText = table.concat(latest, '.')
    if newer(latest, current) then
        return { status='available', latest_version=latestText, release_url=RELEASE_URL }
    end
    return { status='current', latest_version=latestText, release_url=RELEASE_URL }
end

return checker
