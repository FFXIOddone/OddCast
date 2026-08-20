-- SPDX-License-Identifier: GPL-3.0-or-later
-- OddCast's compact copy of the shared OddQ visual language.
local skin = {}
local bit = require('bit')

skin.colors = {
    bg = { 0.063, 0.067, 0.067, 1.00 },
    panel = { 0.094, 0.102, 0.102, 1.00 },
    transparent = { 0.000, 0.000, 0.000, 0.000 },
    blue_border = { 0.059, 0.541, 0.862, 0.72 },
    blue_highlight = { 0.098, 0.858, 1.000, 1.00 },
    text = { 1.000, 1.000, 1.000, 1.00 },
    muted = { 0.700, 0.745, 0.745, 1.00 },
    scrollbar_bg = { 0.039, 0.043, 0.043, 0.82 },
    scrollbar_grab = { 0.059, 0.541, 0.862, 0.40 },
    scrollbar_grab_hovered = { 0.059, 0.541, 0.862, 0.68 },
    scrollbar_grab_active = { 0.098, 0.858, 1.000, 0.84 },
}

local function global(name)
    return _G ~= nil and _G[name] or nil
end

local function push_color(imgui, name, value, pushed)
    local slot = global(name)
    if slot ~= nil and imgui.PushStyleColor ~= nil then
        imgui.PushStyleColor(slot, value)
        pushed.colors = pushed.colors + 1
    end
end

local function push_var(imgui, name, value, pushed)
    local slot = global(name)
    if slot ~= nil and imgui.PushStyleVar ~= nil then
        imgui.PushStyleVar(slot, value)
        pushed.vars = pushed.vars + 1
    end
end

local function add_utf8_codepoints(output, text)
    local index = 1
    while index <= #text do
        local first = string.byte(text, index)
        local codepoint = first
        local width = 1
        if first >= 0xF0 then
            local b2, b3, b4 = string.byte(text, index + 1, index + 3)
            if b2 == nil or b3 == nil or b4 == nil then return false end
            codepoint = bit.bor(bit.lshift(bit.band(first, 0x07), 18), bit.lshift(bit.band(b2, 0x3F), 12), bit.lshift(bit.band(b3, 0x3F), 6), bit.band(b4, 0x3F))
            width = 4
        elseif first >= 0xE0 then
            local b2, b3 = string.byte(text, index + 1, index + 2)
            if b2 == nil or b3 == nil then return false end
            codepoint = bit.bor(bit.lshift(bit.band(first, 0x0F), 12), bit.lshift(bit.band(b2, 0x3F), 6), bit.band(b3, 0x3F))
            width = 3
        elseif first >= 0xC0 then
            local b2 = string.byte(text, index + 1)
            if b2 == nil then return false end
            codepoint = bit.bor(bit.lshift(bit.band(first, 0x1F), 6), bit.band(b2, 0x3F))
            width = 2
        end
        if codepoint > 0xFF and codepoint <= 0xFFFF then output[codepoint] = true end
        index = index + width
    end
    return true
end

local function glyph_ranges(ffi, strings)
    if ffi == nil or ffi.new == nil or type(strings) ~= 'table' then return nil end
    local codepoints = {}
    for _, text in pairs(strings) do
        if type(text) == 'string' and not add_utf8_codepoints(codepoints, text) then return nil end
    end
    local sorted = {}
    for codepoint in pairs(codepoints) do sorted[#sorted + 1] = codepoint end
    table.sort(sorted)
    local values = { 0x20, 0xFF }
    local first, previous = nil, nil
    for _, codepoint in ipairs(sorted) do
        if first == nil then
            first, previous = codepoint, codepoint
        elseif codepoint == previous + 1 then
            previous = codepoint
        else
            values[#values + 1], values[#values + 2] = first, previous
            first, previous = codepoint, codepoint
        end
    end
    if first ~= nil then values[#values + 1], values[#values + 2] = first, previous end
    values[#values + 1] = 0
    local ranges = ffi.new('uint16_t[?]', #values)
    for index, value in ipairs(values) do ranges[index - 1] = value end
    return ranges
end

local function existing_file(paths)
    for _, path in ipairs(paths) do
        local handle = io.open(path, 'rb')
        if handle ~= nil then handle:close(); return path end
    end
    return nil
end

function skin.load_locale_fonts(imgui, ffi, locale_strings, candidates)
    if imgui == nil or imgui.AddFontFromFileTTF == nil then return {} end
    candidates = candidates or {
        ja = { 'C:\\Windows\\Fonts\\meiryo.ttc', 'C:\\Windows\\Fonts\\msgothic.ttc' },
        zh = { 'C:\\Windows\\Fonts\\msyh.ttc', 'C:\\Windows\\Fonts\\simsun.ttc' },
    }
    local loaded = {}
    for _, code in ipairs({ 'ja', 'zh' }) do
        local strings = locale_strings and locale_strings[code] or nil
        local path = existing_file(candidates[code] or {})
        local ranges = glyph_ranges(ffi, strings)
        if path ~= nil and ranges ~= nil then
            local ok, font = pcall(imgui.AddFontFromFileTTF, path, 16.0, nil, ranges)
            if ok and font ~= nil then loaded[code] = { font=font, ranges=ranges, path=path } end
        end
    end
    return loaded
end

function skin.push_locale_font(imgui, loaded, code)
    local record = loaded and loaded[code] or nil
    if record == nil or imgui == nil or imgui.PushFont == nil then return false end
    local ok = pcall(imgui.PushFont, record.font)
    return ok
end

function skin.pop_locale_font(imgui)
    if imgui ~= nil and imgui.PopFont ~= nil then imgui.PopFont() end
end

function skin.push_window(imgui)
    local pushed = { colors = 0, vars = 0 }
    if imgui.SetNextWindowBgAlpha ~= nil then imgui.SetNextWindowBgAlpha(0.93) end
    push_color(imgui, 'ImGuiCol_Text', skin.colors.text, pushed)
    push_color(imgui, 'ImGuiCol_WindowBg', skin.colors.bg, pushed)
    push_color(imgui, 'ImGuiCol_Border', skin.colors.blue_border, pushed)
    push_color(imgui, 'ImGuiCol_TitleBg', skin.colors.transparent, pushed)
    push_color(imgui, 'ImGuiCol_TitleBgActive', skin.colors.transparent, pushed)
    push_color(imgui, 'ImGuiCol_TitleBgCollapsed', skin.colors.transparent, pushed)
    push_color(imgui, 'ImGuiCol_Button', { 0.114, 0.110, 0.086, 0.88 }, pushed)
    push_color(imgui, 'ImGuiCol_ButtonHovered', { 0.059, 0.541, 0.862, 0.62 }, pushed)
    push_color(imgui, 'ImGuiCol_ButtonActive', { 0.098, 0.858, 1.000, 0.72 }, pushed)
    push_color(imgui, 'ImGuiCol_FrameBg', { 0.059, 0.063, 0.063, 0.90 }, pushed)
    push_color(imgui, 'ImGuiCol_ScrollbarBg', skin.colors.scrollbar_bg, pushed)
    push_color(imgui, 'ImGuiCol_ScrollbarGrab', skin.colors.scrollbar_grab, pushed)
    push_color(imgui, 'ImGuiCol_ScrollbarGrabHovered', skin.colors.scrollbar_grab_hovered, pushed)
    push_color(imgui, 'ImGuiCol_ScrollbarGrabActive', skin.colors.scrollbar_grab_active, pushed)
    push_var(imgui, 'ImGuiStyleVar_WindowRounding', 10.0, pushed)
    push_var(imgui, 'ImGuiStyleVar_FrameRounding', 5.0, pushed)
    push_var(imgui, 'ImGuiStyleVar_ScrollbarRounding', 3.0, pushed)
    push_var(imgui, 'ImGuiStyleVar_WindowBorderSize', 0.0, pushed)
    push_var(imgui, 'ImGuiStyleVar_ItemSpacing', { 8.0, 6.0 }, pushed)
    push_var(imgui, 'ImGuiStyleVar_FramePadding', { 4.0, 5.0 }, pushed)
    push_var(imgui, 'ImGuiStyleVar_ButtonTextAlign', { 0.5, 0.5 }, pushed)
    push_var(imgui, 'ImGuiStyleVar_ScrollbarSize', 14.0, pushed)
    return pushed
end

function skin.pop(imgui, pushed)
    if imgui.PopStyleVar ~= nil and pushed.vars > 0 then imgui.PopStyleVar(pushed.vars) end
    if imgui.PopStyleColor ~= nil and pushed.colors > 0 then imgui.PopStyleColor(pushed.colors) end
end

function skin.section_header(imgui, label)
    imgui.Separator()
    if imgui.TextColored ~= nil then
        imgui.TextColored(skin.colors.blue_highlight, label)
    else
        imgui.Text(label)
    end
end

function skin.muted(imgui, text)
    if imgui.TextColored ~= nil then imgui.TextColored(skin.colors.muted, text) else imgui.Text(text) end
end

function skin.button(imgui, label, primary, size)
    local pushed = { colors = 0, vars = 0 }
    if primary then
        push_color(imgui, 'ImGuiCol_Button', { 0.059, 0.541, 0.862, 0.62 }, pushed)
    end
    local clicked
    if size ~= nil then
        clicked = imgui.Button(label, size)
    else
        clicked = imgui.Button(label)
    end
    skin.pop(imgui, pushed)
    return clicked == true
end

return skin
