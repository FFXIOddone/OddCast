-- SPDX-License-Identifier: GPL-3.0-or-later
local checker = {}
local API_URL = 'https://api.github.com/repos/FFXIOddone/OddCast/releases/latest'
local RELEASE_URL = 'https://github.com/FFXIOddone/OddCast/releases/latest'

local function version(value)
    local major, minor, patch = tostring(value or ''):gsub('^OddCast%-v', ''):gsub('^v', ''):match('^(%d+)%.(%d+)%.(%d+)$')
    if major == nil then return nil end
    return { tonumber(major), tonumber(minor), tonumber(patch) }
end

local function safe_path(value)
    value = tostring(value or ''):gsub('/', '\\')
    if value == '' or value:find('["\r\n]') ~= nil then return nil end
    if value:sub(-1) ~= '\\' then value = value .. '\\' end
    return value
end

local function newer(candidate, current)
    for index = 1, 3 do
        if candidate[index] ~= current[index] then return candidate[index] > current[index] end
    end
    return false
end

function checker.begin_install(currentVersion, addonPath, dependencies)
    dependencies = dependencies or {}
    local path = safe_path(addonPath)
    if version(currentVersion) == nil or path == nil then return false, 'invalid updater arguments' end
    local resultPath = (dependencies.tmpname or os.tmpname)()
    if type(resultPath) ~= 'string' or resultPath == '' then return false, 'unable to allocate updater result file' end
    local remove = dependencies.remove or os.remove
    remove(resultPath)
    local script = path .. 'Update-OddCast.ps1'
    local command = string.format(
        'start "" /b powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%s" -CurrentVersion "%s" -AddonPath "%s" -ResultPath "%s"',
        script, currentVersion, path:gsub('\\$', ''), resultPath
    )
    local ok, result = pcall(dependencies.execute or os.execute, command)
    return ok and result ~= nil, resultPath
end

function checker.poll_install(resultPath, dependencies)
    dependencies = dependencies or {}
    local open = dependencies.open or io.open
    local handle = open(resultPath, 'rb')
    if handle == nil then return nil end
    local text = handle:read('*a') or ''
    handle:close()
    local remove = dependencies.remove or os.remove
    remove(resultPath)
    local status, detail = text:match('^(%a+)|([^\r\n]*)$')
    if status ~= 'success' and status ~= 'current' and status ~= 'error' then
        return { status='error', detail='The updater returned an invalid result.' }
    end
    return { status=status, detail=detail }
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
