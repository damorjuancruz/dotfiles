{ ... }:
{
  users.users.jcdamor.extraGroups = [ "libvirtd" ];
  virtualisation.libvirtd.enable = true;

  programs.virt-manager.enable = true;
}
