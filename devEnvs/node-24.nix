{ pkgs }:

pkgs.mkShell {
  packages = with pkgs; [
    nodejs_24
    pnpm
    yarn
  ];

  shellHook = "exec fish";
}
