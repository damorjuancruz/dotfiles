{ pkgs }:

pkgs.mkShell {
  packages = with pkgs; [
    nodejs_24
    pnpm
    yarn
    openssl
  ];

  shellHook = with pkgs; ''
    export PRISMA_SCHEMA_ENGINE_BINARY="${prisma-engines}/bin/schema-engine"
    export PRISMA_QUERY_ENGINE_BINARY="${prisma-engines}/bin/query-engine"
    export PRISMA_QUERY_ENGINE_LIBRARY="${prisma-engines}/lib/libquery_engine.node"
    export PRISMA_FMT_BINARY="${prisma-engines}/bin/prisma-fmt"
    exec fish
  '';
}
