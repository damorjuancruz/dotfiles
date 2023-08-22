// importing
const { Hyprland, Notifications, Mpris, Audio, Battery } = ags.Service;
const { exec, CONFIG_DIR, USER, execAsync } = ags.Utils;

const workspaces = {
  type: 'box',
  className: 'workspaces',
  connections: [[Hyprland, box => {
    // remove every children
    box.get_children().forEach(ch => ch.destroy());

    // add a button for each workspace
    const workspaces = 5;
    for (let i = 1; i <= workspaces; ++i) {
      const child = Hyprland.workspaces.get(i) ? '●' : '○'
      box.add(ags.Widget({
        type: 'button',
        onClick: () => execAsync(`/home/${USER}/.config/hypr/scripts/switch-workspace.sh ${i}`),
        child,
        className: Hyprland.active.workspace.id == i ? 'focused' : '',
      }));
    }

    // make the box render it
    box.show_all();
  }]],
};

const clock = {
  type: 'label',
  className: 'clock',
  connections: [[1000, label => label.label = exec('date +"%A, %B %d · %R"').trim()]],
};

const notification = {
  type: 'box',
  className: 'notification',
  connections: [[Notifications, box => box.visible = Notifications.popups.size > 0]],
  children: [
    {
      type: 'icon',
      className: 'icon',
      icon: 'preferences-system-notifications-symbolic',
    },
    {
      type: 'label',
      className: 'label',
      connections: [[Notifications, label => {
        // notifications is a map, to get the last elememnt lets make an array
        label.label = Array.from(Notifications.popups)?.pop()?.[1].summary || '';
      }]],
    },
  ],
};

const media = {
  type: 'label',
  className: 'media',
  connections: [[Mpris, label => {
    const mpris = Mpris.getPlayer('');
    if (mpris)
      label.label = `${mpris.trackArtists.join(', ')} - ${mpris.trackTitle}`;
    else
      label.label = 'Nothing is playing';
  }]],
};

const volume = {
  type: 'box',
  className: 'volume',
  children: [
    {
      type: 'dynamic',
      items: [
        { value: 101, widget: { type: 'icon', className: 'icon', icon: 'audio-volume-overamplified-symbolic' } },
        { value: 67, widget: { type: 'icon', className: 'icon', icon: 'audio-volume-high-symbolic' } },
        { value: 34, widget: { type: 'icon', className: 'icon', icon: 'audio-volume-medium-symbolic' } },
        { value: 1, widget: { type: 'icon', className: 'icon', icon: 'audio-volume-low-symbolic' } },
        { value: 0, widget: { type: 'icon', className: 'icon', icon: 'audio-volume-muted-symbolic' } },
      ],
      // dynamic is a Gtk.Box with an extra update method
      connections: [[Audio, dynamic => dynamic.update(value => {
        if (!Audio.speaker)
          return;

        if (Audio.speaker.isMuted)
          return value === 0;

        return value <= (Audio.speaker.volume * 100);
      }), 'speaker-changed']],
    },
    {
      type: 'label',
      connections: [[Audio, label => {
        if (!Audio.speaker)
          return

        label.label = `${Math.round(Audio.speaker.volume * 100)}%`
      }]],
    },
  ],
};

const battery = {
  type: 'box',
  className: 'battery',
  children: [
    {
      type: 'icon',
      className: 'icon',
      connections: [[Battery, icon => icon.icon_name = `battery-level-${Math.floor(Battery.percent / 10) * 10}-symbolic`]]
    },
    {
      type: 'label',
      connections: [[Battery, label => label.label = `${Battery.percent}%`]],
    },
  ],
};

// layout of the bar
const left = {
  type: 'box',
  className: 'left',
  children: [
    workspaces,
  ],
};

const center = {
  type: 'box',
  className: 'center',
  children: [
    clock,
  ],
};

const right = {
  type: 'box',
  className: 'right',
  halign: 'end',
  children: [
    notification,
    volume,
    battery,
  ],
};

const bar = {
  name: 'bar',
  anchor: ['top', 'left', 'right'],
  exclusive: true,
  child: {
    type: 'centerbox',
    className: 'bar',
    children: [
      left,
      center,
      right,
    ],
  },
}

// exporting the config
var config = {
  style: CONFIG_DIR + '/style.css',
  windows: [bar],
};
