# Do not modify this file!  It was generated by ‘nixos-generate-config’
# and may be overwritten by future invocations.  Please make changes
# to /etc/nixos/configuration.nix instead.
{ config, lib, pkgs, modulesPath, ... }:

{
  imports =
    [ (modulesPath + "/installer/scan/not-detected.nix")
    ];

  boot.initrd.availableKernelModules = [ "xhci_pci" "ahci" "nvme" "usbhid" "usb_storage" "sd_mod" "rtsx_usb_sdmmc" ];
  boot.initrd.kernelModules = [ ];
  boot.kernelModules = [ "kvm-intel" ];
  boot.extraModulePackages = [ ];

  fileSystems."/" =
    { device = "/dev/disk/by-uuid/fd682c51-7a0d-4f75-8d53-6aa14ff5efb7";
      fsType = "ext4";
    };

  boot.initrd.luks.devices = {
    "luks-root".device = "/dev/disk/by-uuid/974985ba-1931-43cd-b1b4-890c4664cf82";
    "luks-swap".device = "/dev/disk/by-uuid/d3881360-1c94-4529-bc7d-17a5f4c4d679";
  };

  fileSystems."/boot" =
    { device = "/dev/disk/by-uuid/53F0-6B54";
      fsType = "vfat";
    };

  swapDevices = [
    { device = "/dev/disk/by-uuid/3a75e652-f833-4418-b1c6-ef7335b28a88"; }
  ];

  # Enables DHCP on each ethernet and wireless interface. In case of scripted networking
  # (the default) this is the recommended approach. When using systemd-networkd it's
  # still possible to use this option, but it's recommended to use it in conjunction
  # with explicit per-interface declarations with `networking.interfaces.<interface>.useDHCP`.
  networking.useDHCP = lib.mkDefault true;
  # networking.interfaces.wlo1.useDHCP = lib.mkDefault true;

  nixpkgs.hostPlatform = lib.mkDefault "x86_64-linux";
  hardware.cpu.intel.updateMicrocode = lib.mkDefault config.hardware.enableRedistributableFirmware;
}