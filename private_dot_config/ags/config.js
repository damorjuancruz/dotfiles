import Widget from 'resource:///com/github/Aylur/ags/widget.js';
import App from 'resource:///com/github/Aylur/ags/app.js';
import { exec, execAsync, USER } from 'resource:///com/github/Aylur/ags/utils.js';

// services
import Hyprland from 'resource:///com/github/Aylur/ags/service/hyprland.js';
import SystemTray from 'resource:///com/github/Aylur/ags/service/systemtray.js';
import Audio from 'resource:///com/github/Aylur/ags/service/audio.js';
import Battery from 'resource:///com/github/Aylur/ags/service/battery.js';
import Notifications from 'resource:///com/github/Aylur/ags/service/notifications.js';

const workspaces = () => Widget.Box({
  className: 'workspaces',
  connections: [
    [Hyprland, self => {
      self.children = Array.from({ length: 5 }, (_, i) => i + 1).map((i) => Widget.Button({
        onClicked: () => execAsync(
          `/home/${USER}/.config/hypr/scripts/switch-workspace.sh ${i}`
        ),
        child: Widget.Label(Hyprland.getWorkspace(i) ? '●' : '○'),
        className: Hyprland.active.workspace.id == i ? 'focused' : '',
      }))
    }]
  ]
})

const clock = () => Widget.Label({
  className: 'clock',
  connections: [
    [1000, async (self) => {
      self.label = await execAsync(['date', '+%A, %B %d · %R'])
    }]
  ],
})

const notifications = () => Widget.Box({
  className: 'notification',
  connections: [
    [Notifications, self => self.visible = Notifications.popups.length > 0]
  ],
  children: [
    Widget.Icon({
      className: 'icon',
      icon: 'preferences-system-notifications-symbolic',
    }),
    Widget.Label({
      className: 'label',
      connections: [
        [Notifications, self => {
          self.label = Notifications.popups.slice(-1)[0]?.summary ?? ''
        }]
      ],
    }),
  ],
})
const systray = () => Widget.Box({
  connections: [[SystemTray, self => {
    self.children = SystemTray.items.map(item => Widget.Button({
      child: Widget.Icon({
        className: 'icon',
        binds: [['icon', item, 'icon']]
      }),
      onPrimaryClick: (_, event) => item.activate(event),
      onSecondaryClick: (_, event) => item.openMenu(event),
      binds: [['tooltip-markup', item, 'tooltip-markup']],
    }));
  }]],
});
const volume = () => Widget.Button({
  className: 'volume',
  onClicked: () => execAsync(
    ['wpctl', 'set-mute', '@DEFAULT_AUDIO_SINK@', 'toggle']
  ),
  child: Widget.Icon({
    className: 'icon',
    connections: [[Audio, self => {
      if (!Audio.speaker)
        return;

      const vol = Audio.speaker.volume * 100;
      const icon = Audio.speaker.stream.isMuted
        ? 'muted'
        : [
          [101, 'overamplified'],
          [67, 'high'],
          [34, 'medium'],
          [1, 'low'],
          [0, 'muted'],
        ].find(([threshold]) => threshold <= vol)[1];

      self.icon = `audio-volume-${icon}-symbolic`;
      self.tooltipText = `${Math.floor(vol)}%`;
    }, 'speaker-changed']],
  }),
});
const battery = () => Widget.Box({
  className: 'battery',
  children: [
    Widget.Icon({
      className: 'icon',
      connections: [
        [Battery, self => {
          self.icon_name = `battery-level-${Math.floor(Battery.percent / 10) * 10}-symbolic`
        }]
      ]
    }),
    Widget.Label({
      connections: [[Battery, label => label.label = `${Battery.percent}%`]],
    }),
  ],
})

const left = () => Widget.Box({
  className: 'left',
  children: [
    workspaces(),
  ]
})
const center = () => Widget.Box({
  className: 'center',
  children: [
    clock(),
  ],
})
const right = () => Widget.Box({
  className: 'right',
  hpack: 'end',
  children: [
    notifications(),
    systray(),
    volume(),
    battery(),
  ]
})

const barWindow = ({ monitor } = {}) => Widget.Window({
  name: `bar-${monitor}`,
  monitor,
  anchor: ['top', 'left', 'right'],
  exclusivity: 'exclusive',
  child: Widget.CenterBox({
    className: 'bar',
    start_widget: left(),
    center_widget: center(),
    end_widget: right(),
  })
});

const monitors = JSON.parse(exec('hyprctl monitors -j'))
export default {
  // closeWindowDelay: {
  //   'window-name': 500, // milliseconds
  // },
  // notificationPopupTimeout: 5000, // milliseconds
  // cacheNotificationActions: false,
  // maxStreamVolume: 1.5, // float
  style: App.configDir + '/style.css',
  windows: monitors.map(({ id }) => barWindow({ monitor: id })),
};
