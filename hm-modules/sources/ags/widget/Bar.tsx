import { App, Astal, Gtk, Gdk } from "astal/gtk4"
import { Variable, GLib, bind } from "astal"
import Hyprland from "gi://AstalHyprland"
import Mpris from "gi://AstalMpris"
import Battery from "gi://AstalBattery"
import Wp from "gi://AstalWp"
import Network from "gi://AstalNetwork"
import Tray from "gi://AstalTray"

function Time({ format = "%A, %B %d · %R" }) {
  const time = Variable<string>("").poll(
    1000,
    () => GLib.DateTime.new_now_local().format(format)!
  )

  return <menubutton onDestroy={() => time.drop()}>
    <label
      className="time"
      label={time()}
    />
    <popover>
      <Gtk.Calendar />
    </popover>
  </menubutton>
}

function SysTray() {
  const tray = Tray.get_default()

  return <box className="sys-tray">
    {bind(tray, "items").as(items =>
      items.map(item => (
        <button
          onClicked={() => item.activate(0, 0)}
        >
          <image gicon={bind(item, "gicon")} />
        </button>
      ))
     )}
  </box>
        // <menubutton
        //   tooltipMarkup={bind(item, "tooltipMarkup")}
        // actionGroup={bind(item, "actionGroup").as(ag => ["dbusmenu", ag])}
        //   menuModel={bind(item, "menuModel")}
        // >
        //   <image gicon={bind(item, "gicon")} />
        // </menubutton>
}

export default function Bar(gdkmonitor: Gdk.Monitor) {
  const { TOP, LEFT, RIGHT } = Astal.WindowAnchor

  return (
    <window
      visible
      cssClasses={["bar"]}
      gdkmonitor={gdkmonitor}
      exclusivity={Astal.Exclusivity.EXCLUSIVE}
      anchor={TOP | LEFT | RIGHT}
      application={App}
    >
      <centerbox>
        <box hexpand halign={Gtk.Align.START}>
          <label label='asdf' />

          {/*
          <Workspaces />
          <FocusedClient />
          */}
        </box>
        <box>
          {/*
          <Media />
          */}
          <Time />
        </box>
        <box hexpand halign={Gtk.Align.END} >
          {/*
          <Wifi />
          <AudioSlider />
          <BatteryLevel />
          */}
          <SysTray />
        </box>
      </centerbox>
    </window>
  )
}
