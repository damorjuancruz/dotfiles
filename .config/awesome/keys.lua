local awful = require("awful")
local hotkeys_popup = require("awful.hotkeys_popup")
-- Enable hotkeys help widget for VIM and other apps
-- when client with a matching name is opened:
require("awful.hotkeys_popup.keys")
local menubar = require("menubar")

local terminal = "alacritty"
local editor = os.getenv("EDITOR") or "nano"
local editor_cmd = terminal .. " -e " .. editor
local visualEditor = "code"
local modkey = "Mod4"

-- {{{ Key bindings
awful.keyboard.append_global_keybindings({
  awful.key(
    { modkey, "Mod1" }, "s",
    hotkeys_popup.show_help,
    { description = "show help", group = "awesome" }
  ),

  awful.key(
    { modkey }, "j",
    function() awful.client.focus.byidx(1) end,
    { description = "focus next by index", group = "client" }
  ),
  awful.key(
    { modkey }, "k",
    function() awful.client.focus.byidx(-1) end,
    { description = "focus previous by index", group = "client" }
  ),

  -- Layout manipulation
  awful.key(
    { modkey, "Shift" }, "j",
    function() awful.client.swap.byidx(1) end,
    { description = "swap with next client by index", group = "client" }
  ),
  awful.key(
    { modkey, "Shift" }, "k",
    function() awful.client.swap.byidx(-1) end,
    { description = "swap with previous client by index", group = "client" }
  ),
  awful.key(
    { modkey }, "s",
    function() awful.screen.focus_relative(1) end,
    { description = "focus the next screen", group = "screen" }
  ),
  awful.key(
    { modkey }, "a",
    awful.client.urgent.jumpto,
    { description = "jump to client requesting attention", group = "client" }
  ),
  awful.key(
    { modkey }, "Tab",
    function()
      awful.client.focus.history.previous()
      if client.focus then
        client.focus:raise()
      end
    end,
    { description = "go back", group = "client" }
  ),

  -- Standard program
  awful.key(
    { modkey }, "Return",
    function() awful.spawn(terminal) end,
    { description = "open a terminal", group = "launcher" }
  ),
  awful.key(
    { modkey }, "e",
    function() awful.spawn(editor_cmd) end,
    { description = "open editor", group = "launcher" }
  ),
  awful.key(
    { modkey }, "c",
    function() awful.spawn(visualEditor) end,
    { description = "open visual editor", group = "launcher" }
  ),
  awful.key(
    { modkey }, "w",
    function() awful.spawn(visualEditor) end,
    { description = "open web browser", group = "launcher" }
  ),
  awful.key(
    { modkey, "Control" }, "r",
    awesome.restart,
    { description = "reload awesome", group = "awesome" }
  ),
  awful.key(
    { modkey, "Shift" }, "q",
    awesome.quit,
    { description = "quit awesome", group = "awesome" }
  ),

  awful.key(
    { modkey }, "l",
    function() awful.tag.incmwfact(0.05) end,
    { description = "increase master width factor", group = "layout" }
  ),
  awful.key(
    { modkey }, "h",
    function() awful.tag.incmwfact(-0.05) end,
    { description = "decrease master width factor", group = "layout" }
  ),
  awful.key(
    { modkey, "Shift" }, "h",
    function() awful.tag.incnmaster(1, nil, true) end,
    { description = "increase the number of master clients", group = "layout" }
  ),
  awful.key(
    { modkey, "Shift" }, "l",
    function() awful.tag.incnmaster(-1, nil, true) end,
    { description = "decrease the number of master clients", group = "layout" }
  ),
  awful.key(
    { modkey, "Control" }, "h",
    function() awful.tag.incncol(1, nil, true) end,
    { description = "increase the number of columns", group = "layout" }
  ),
  awful.key(
    { modkey, "Control" }, "l",
    function() awful.tag.incncol(-1, nil, true) end,
    { description = "decrease the number of columns", group = "layout" }
  ),
  awful.key(
    { modkey }, "space",
    function() awful.layout.inc(1) end,
    { description = "select next", group = "layout" }
  ),
  awful.key(
    { modkey, "Shift" }, "space",
    function() awful.layout.inc(-1) end,
    { description = "select previous", group = "layout" }
  ),

  awful.key(
    { modkey, "Control" }, "n",
    function()
      local c = awful.client.restore()
      -- Focus restored client
      if c then
        c:emit_signal(
          "request::activate", "key.unminimize", { raise = true }
        )
      end
    end,
    { description = "restore minimized", group = "client" }
  ),

  -- Prompt
  awful.key(
    { modkey }, "r",
    function() awful.screen.focused().mypromptbox:run() end,
    { description = "run prompt", group = "launcher" }
  ),

  awful.key(
    { modkey }, "x",
    function()
      awful.prompt.run {
        prompt       = "Run Lua code: ",
        textbox      = awful.screen.focused().mypromptbox.widget,
        exe_callback = awful.util.eval,
        history_path = awful.util.get_cache_dir() .. "/history_eval"
      }
    end,
    { description = "lua execute prompt", group = "awesome" }
  ),
  -- Menubar
  awful.key(
    { modkey, "Shift" }, "Return",
    function() menubar.show() end,
    { description = "show the menubar", group = "launcher" }
  ),
})

-- Tags
local tag_keys = { "u", "i", "o", "p", "[" }
for index, value in ipairs(tag_keys) do
  awful.keyboard.append_global_keybindings({
    -- View tag only.
    awful.key(
      { modkey }, value,
      function()
        local tag = awful.screen.focused().tags[index]
        if tag then
          tag:view_only()
        end
      end,
      { description = "view tag #" .. index .. " only", group = "tag" }
    ),

    -- Toggle tag display.
    awful.key(
      { modkey, "Control" }, value,
      function()
        local tag = awful.screen.focused().tags[index]
        if tag then
          awful.tag.viewtoggle(tag)
        end
      end,
      { description = "toggle display of tag #" .. index, group = "tag" }
    ),

    -- Move client to tag.
    awful.key(
      { modkey, "Shift" }, value,
      function()
        local tag = client.focus.screen.tags[index]
        if tag then
          client.focus:move_to_tag(tag)
        end
      end,
      { description = "move focused client to tag #" .. index, group = "tag" }
    ),

    -- Toggle focused client on tag
    awful.key(
      { modkey, "Control", "Shift" }, value,
      function()
        local tag = client.focus.screen.tags[index]
        if tag then
          client.focus:toggle_tag(tag)
        end
      end,
      { description = "toggle display of focused client on tag #" .. index, group = "tag" }
    ),
  })
end

awful.keyboard.append_global_keybindings({
  -- Volume keys
  awful.key(
    {}, "XF86AudioRaiseVolume",
    function() awful.spawn("pamixer -i 5", false) end,
    { description = "increase volume", group = "control" }
  ),
  awful.key(
    {}, "XF86AudioLowerVolume",
    function() awful.spawn("pamixer -d 5", false) end,
    { description = "decrease volume", group = "control" }
  ),

  awful.key(
    {}, "XF86AudioMute",
    function() awful.spawn("pamixer -t", false) end,
    { description = "toggle mute volume", group = "control" }
  ),

  -- Brightness keys
  awful.key(
    {}, "XF86MonBrightnessUp",
    function() awful.spawn("brightnessctl set 2.5%+ -q", false) end,
    { description = "increase brightness", group = "control" }
  ),
  awful.key(
    {}, "XF86MonBrightnessDown",
    function() awful.spawn("brightnessctl set 2.5%- -q", false) end,
    { description = "decrease brightness", group = "control" }
  )
})

client.connect_signal("request::default_keybindings", function()
  awful.keyboard.append_client_keybindings({
    awful.key(
      { modkey }, "f",
      function(c)
        c.fullscreen = not c.fullscreen
        c:raise()
      end,
      { description = "toggle fullscreen", group = "client" }
    ),
    awful.key(
      { modkey }, "q",
      function(c) c:kill() end,
      { description = "close", group = "client" }
    ),
    awful.key(
      { modkey, "Control" }, "space",
      awful.client.floating.toggle,
      { description = "toggle floating", group = "client" }
    ),
    awful.key(
      { modkey, "Control" }, "Return",
      function(c) c:swap(awful.client.getmaster()) end,
      { description = "move to master", group = "client" }
    ),
    awful.key(
      { modkey, "Shift" }, "s",
      function(c) c:move_to_screen() end,
      { description = "move to next screen", group = "client" }
    ),
    awful.key(
      { modkey }, "t",
      function(c) c.ontop = not c.ontop end,
      { description = "toggle keep on top", group = "client" }
    ),
    awful.key(
      { modkey }, "n",
      function(c)
        -- The client currently has the input focus, so it cannot be
        -- minimized, since minimized clients can't have the focus.
        c.minimized = true
      end,
      { description = "minimize", group = "client" }
    ),
    awful.key(
      { modkey }, "m",
      function(c)
        c.maximized = not c.maximized
        c:raise()
      end,
      { description = "toggle maximize", group = "client" }
    ),
  })
end)

client.connect_signal("request::default_mousebindings", function()
  awful.mouse.append_client_mousebindings({
    awful.button(
      {}, 1,
      function(c) c:emit_signal("request::activate", "mouse_click", { raise = true }) end
    ),
    awful.button(
      { modkey }, 1,
      function(c)
        c:emit_signal("request::activate", "mouse_click", { raise = true })
        awful.mouse.client.move(c)
      end
    ),
    awful.button(
      { modkey }, 3,
      function(c)
        c:emit_signal("request::activate", "mouse_click", { raise = true })
        awful.mouse.client.resize(c)
      end
    )
  })
end)
