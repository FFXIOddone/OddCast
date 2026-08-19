-- SPDX-License-Identifier: GPL-3.0-or-later
-- OddCast's compact copy of the shared OddQ visual language.
local skin = {}

skin.colors = {
    bg = { 0.063, 0.067, 0.067, 1.00 },
    panel = { 0.094, 0.102, 0.102, 1.00 },
    blue_border = { 0.059, 0.541, 0.862, 0.72 },
    blue_highlight = { 0.098, 0.858, 1.000, 1.00 },
    text = { 0.933, 0.914, 0.863, 1.00 },
    muted = { 0.700, 0.745, 0.745, 1.00 },
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

function skin.push_window(imgui)
    local pushed = { colors = 0, vars = 0 }
    if imgui.SetNextWindowBgAlpha ~= nil then imgui.SetNextWindowBgAlpha(0.93) end
    push_color(imgui, 'ImGuiCol_Text', skin.colors.text, pushed)
    push_color(imgui, 'ImGuiCol_WindowBg', skin.colors.bg, pushed)
    push_color(imgui, 'ImGuiCol_Border', skin.colors.blue_border, pushed)
    push_color(imgui, 'ImGuiCol_TitleBg', skin.colors.panel, pushed)
    push_color(imgui, 'ImGuiCol_TitleBgActive', skin.colors.panel, pushed)
    push_color(imgui, 'ImGuiCol_Button', { 0.114, 0.110, 0.086, 0.88 }, pushed)
    push_color(imgui, 'ImGuiCol_ButtonHovered', { 0.059, 0.541, 0.862, 0.62 }, pushed)
    push_color(imgui, 'ImGuiCol_ButtonActive', { 0.098, 0.858, 1.000, 0.72 }, pushed)
    push_color(imgui, 'ImGuiCol_FrameBg', { 0.059, 0.063, 0.063, 0.90 }, pushed)
    push_var(imgui, 'ImGuiStyleVar_WindowRounding', 10.0, pushed)
    push_var(imgui, 'ImGuiStyleVar_FrameRounding', 5.0, pushed)
    push_var(imgui, 'ImGuiStyleVar_WindowBorderSize', 0.0, pushed)
    push_var(imgui, 'ImGuiStyleVar_ItemSpacing', { 8.0, 6.0 }, pushed)
    push_var(imgui, 'ImGuiStyleVar_FramePadding', { 4.0, 5.0 }, pushed)
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
    local clicked = size ~= nil and imgui.Button(label, size) or imgui.Button(label)
    skin.pop(imgui, pushed)
    return clicked == true
end

return skin
