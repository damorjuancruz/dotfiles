{ config, pkgs, inputs, ... }:

{
  imports = [ inputs.home-manager.nixosModules.default ];

  home-manager.useUserPackages = true;
  home-manager.useGlobalPkgs = true;
  home-manager = {
    extraSpecialArgs = { inherit inputs; };
    users = {
      jcdamor = import ./jcdamor.nix;
    };
  };
}
