-- If LuaRocks is installed, make sure that packages installed through it are
-- found (e.g. lgi). If LuaRocks is not installed, do nothing.
pcall(require, "luarocks.loader")

-- Standard awesome library
local gears = require("gears")
local awful = require("awful")
require("awful.autofocus")
-- Widget and layout library
local wibox = require("wibox")
-- Theme handling library
local beautiful = require("beautiful")
local dpi = beautiful.xresources.apply_dpi
-- Notification library
local naughty = require("naughty")
local menubar = require("menubar")

-- {{{ Error handling
-- Check if awesome encountered an error during startup and fell back to
-- another config (This code will only ever execute for the fallback config)
if awesome.startup_errors then
  naughty.notify({ preset = naughty.config.presets.critical,
    title = "Oops, there were errors during startup!",
    text = awesome.startup_errors })
end

-- Handle runtime errors after startup
do
  local in_error = false
  awesome.connect_signal("debug::error", function(err)
    -- Make sure we don't go into an endless error loop
    if in_error then return end
    in_error = true

    naughty.notify({ preset = naughty.config.presets.critical,
      title = "Oops, an error happened!",
      text = tostring(err) })
    in_error = false
  end)
end
-- }}}

-- {{{ Variable definitions
-- Themes define colours, icons, font and wallpapers.
beautiful.init(gears.filesystem.get_configuration_dir() .. "themes/default/theme.lua")

-- This is used later as the default terminal and editor to run.
terminal = "alacritty"
editor = os.getenv("EDITOR") or "nano"
editor_cmd = terminal .. " -e " .. editor

-- Default modkey.
-- Usually, Mod4 is the key with a logo between Control and Alt.
-- If you do not like this or do not have such a key,
-- I suggest you to remap Mod4 to another key using xmodmap or other tools.
-- However, you can use another modifier like Mod1, but it may interact with others.
modkey = "Mod4"

-- Table of layouts to cover with awful.layout.inc, order matters.
awful.layout.layouts = {
  awful.layout.suit.tile,
  awful.layout.suit.max,
  awful.layout.suit.floating,
  -- awful.layout.suit.corner.nw,
  -- awful.layout.suit.fair.horizontal,
  -- awful.layout.suit.tile.left,
  -- awful.layout.suit.tile.bottom,
  -- awful.layout.suit.tile.top,
  -- awful.layout.suit.fair,
  -- awful.layout.suit.spiral,
  -- awful.layout.suit.spiral.dwindle,
  -- awful.layout.suit.max.fullscreen,
  -- awful.layout.suit.magnifier,
  -- awful.layout.suit.corner.ne,
  -- awful.layout.suit.corner.sw,
  -- awful.layout.suit.corner.se,
}
-- }}}

-- {{{ Menu
-- Menubar configuration
menubar.utils.terminal = terminal -- Set the terminal for applications that require it
-- }}}

-- Keyboard map indicator and switcher
mykeyboardlayout = awful.widget.keyboardlayout()

-- {{{ Wibar
-- Create a textclock widget
mytextclock = wibox.widget.textclock()

-- Create a wibox for each screen and add it
local taglist_buttons = gears.table.join(
  awful.button(
    {}, 1, -- left click
    function(t) t:view_only() end-- view tag only
  ),
  awful.button(
    { modkey }, 1, -- mod + left click
    function(t)
      if client.focus then
        client.focus:move_to_tag(t) -- move focused client to tag
      end
    end
  ),
  awful.button(
    {}, 3, -- right click
    awful.tag.viewtoggle-- view tag toggle
  ),
  awful.button(
    { modkey }, 3, -- mod + right click
    function(t)
      if client.focus then
        client.focus:toggle_tag(t) -- toggle focused client on tag
      end
    end
  ),
  -- scroll through tags
  awful.button(
    {}, 4,
    function(t) awful.tag.viewnext(t.screen) end
  ),
  awful.button(
    {}, 5,
    function(t) awful.tag.viewprev(t.screen) end
  )
)

local function set_wallpaper(s)
  -- Wallpaper
  if beautiful.wallpaper then
    local wallpaper = beautiful.wallpaper
    -- If wallpaper is a function, call it with the screen
    if type(wallpaper) == "function" then
      wallpaper = wallpaper(s)
    end
    gears.wallpaper.maximized(wallpaper, s)
  end
end

-- Re-set wallpaper when a screen's geometry changes (e.g. different resolution)
screen.connect_signal("property::geometry", set_wallpaper)

awful.screen.connect_for_each_screen(function(s)
  -- Wallpaper
  set_wallpaper(s)

  -- Each screen has its own tag table.
  awful.tag({ "WWW", "DEV", "TTY", "COM", "ETC" }, s, awful.layout.layouts[1])

  -- Create a promptbox for each screen
  s.mypromptbox = awful.widget.prompt()
  -- Create an imagebox widget which will contain an icon indicating which layout we're using.
  -- We need one layoutbox per screen.
  s.mylayoutbox = awful.widget.layoutbox(s)
  s.mylayoutbox:buttons(gears.table.join(
    awful.button({}, 1, function() awful.layout.inc(1) end),
    awful.button({}, 3, function() awful.layout.inc(-1) end),
    awful.button({}, 4, function() awful.layout.inc(1) end),
    awful.button({}, 5, function() awful.layout.inc(-1) end)))
  -- Create a taglist widget
  s.mytaglist = awful.widget.taglist {
    screen  = s,
    filter  = awful.widget.taglist.filter.all,
    buttons = taglist_buttons
  }

  local screen_width = s.geometry.width
  -- Create the wibox
  s.mywibox = awful.wibar({
    screen = s,
    height = dpi(32),
    width = screen_width - beautiful.useless_gap * 4,
    shape = function(cr, width, height)
      gears.shape.rounded_rect(cr, width, height, beautiful.rounded)
    end,
  })

  awful.placement.top(s.mywibox, {
    margins = beautiful.useless_gap * 2
  })

  s.mywibox:struts({
    top = s.mywibox.height + beautiful.useless_gap * 2
  })

  local batteryarc_widget = require('widgets.batteryarc')

  -- Add widgets to the wibox
  s.mywibox:setup {
    layout = wibox.layout.align.horizontal,
    expand = "none",
    { -- Left widgets
      layout = wibox.layout.fixed.horizontal,
      s.mytaglist,
      s.mypromptbox,
    },
    { -- Middle widget
      layout = wibox.layout.fixed.horizontal,
      mytextclock,
    },
    { -- Right widgets
      spacing = dpi(8),
      layout = wibox.layout.fixed.horizontal,
      mykeyboardlayout,
      {
        wibox.widget.systray(),
        widget = wibox.container.margin,
        margins = { bottom = dpi(4), top = dpi(4) },
      },
      batteryarc_widget({
        show_current_level = true,
        font = "Nunito, Bold, 6"
      }),
      s.mylayoutbox,
    },
  }
end)
-- }}}

require("keys")

require("rules")

-- {{{ Signals
-- Signal function to execute when a new client appears.
client.connect_signal("manage", function(c)
  -- Set the windows at the slave,
  -- i.e. put it at the end of others instead of setting it master.
  -- if not awesome.startup then awful.client.setslave(c) end

  if awesome.startup
      and not c.size_hints.user_position
      and not c.size_hints.program_position then
    -- Prevent clients from being unreachable after screen count changes.
    awful.placement.no_offscreen(c)
  end
end)

-- Add a titlebar if titlebars_enabled is set to true in the rules.
client.connect_signal("request::titlebars", function(c)
  -- buttons for the titlebar
  local buttons = gears.table.join(
    awful.button({}, 1, function()
      c:emit_signal("request::activate", "titlebar", { raise = true })
      awful.mouse.client.move(c)
    end),
    awful.button({}, 3, function()
      c:emit_signal("request::activate", "titlebar", { raise = true })
      awful.mouse.client.resize(c)
    end)
  )

  awful.titlebar(c):setup {
    { -- Left
      awful.titlebar.widget.iconwidget(c),
      buttons = buttons,
      layout  = wibox.layout.fixed.horizontal
    },
    { -- Middle
      { -- Title
        align  = "center",
        widget = awful.titlebar.widget.titlewidget(c)
      },
      buttons = buttons,
      layout  = wibox.layout.flex.horizontal
    },
    { -- Right
      awful.titlebar.widget.floatingbutton(c),
      awful.titlebar.widget.maximizedbutton(c),
      awful.titlebar.widget.stickybutton(c),
      awful.titlebar.widget.ontopbutton(c),
      awful.titlebar.widget.closebutton(c),
      layout = wibox.layout.fixed.horizontal()
    },
    layout = wibox.layout.align.horizontal,
  }
end)

-- Enable sloppy focus, so that focus follows mouse.
client.connect_signal("mouse::enter", function(c)
  c:emit_signal("request::activate", "mouse_enter", { raise = false })
end)

client.connect_signal("focus", function(c) c.border_color = beautiful.border_focus end)
client.connect_signal("unfocus", function(c) c.border_color = beautiful.border_normal end)
-- }}}

-- autostart
-- startup apps runner
local function run(command, pidof)
  -- emended from manilarome
  local findme = command
  local firstspace = command:find(' ')
  if firstspace then
    findme = command:sub(0, firstspace - 1)
  end

  awful.spawn.easy_async_with_shell(string.format('/bin/sh -c "pgrep -u $USER -x %s > /dev/null || (%s &)"',
    pidof or findme, command))
end

local applications = {
  "picom",
  "telegram-desktop",
  "discord",
  "firefox",
}

for _, prc in ipairs(applications) do
  run(prc)
end
