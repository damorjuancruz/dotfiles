{
  description = "NixOS configuration";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-25.05";
    nixpkgs-unstable.url = "github:nixos/nixpkgs/nixos-unstable";
    home-manager.url = "github:nix-community/home-manager/release-25.05";
    home-manager.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs =
    inputs@{
      nixpkgs,
      nixpkgs-unstable,
      home-manager,
      ...
    }:
    let
      devEnvDir = ./devEnvs;
      devEnvs =
        let
          files = builtins.attrNames (builtins.readDir devEnvDir);
          nixFiles = builtins.filter (f: builtins.match ".*\\.nix$" f != null) files;
        in
        builtins.listToAttrs (
          map (file: {
            name = builtins.replaceStrings [ ".nix" ] [ "" ] file;
            value = import (devEnvDir + "/${file}") { pkgs = nixpkgs-unstable.legacyPackages."x86_64-linux"; };
          }) nixFiles
        );
    in
    {
      devShells."x86_64-linux" = devEnvs;

      nixosConfigurations.laptop = nixpkgs.lib.nixosSystem {
        specialArgs = { inherit inputs; };
        system = "x86_64-linux";
        modules = [
          {
            nixpkgs.overlays = [
              (final: prev: {
                # unstable = nixpkgs-unstable.legacyPackages.${prev.system};
                # use this variant if unfree packages are needed:
                unstable = import nixpkgs-unstable {
                  inherit prev;
                  system = prev.system;
                  config.allowUnfree = true;
                };
              })
            ];
          }
          ./configuration.nix
          ./hardware-configuration.nix
          home-manager.nixosModules.home-manager
          {
            home-manager.useGlobalPkgs = true;
            home-manager.useUserPackages = true;
            home-manager.users.jcdamor = import ./home.nix;
            home-manager.extraSpecialArgs = { inherit inputs; };
          }
        ];
      };
    };
}
