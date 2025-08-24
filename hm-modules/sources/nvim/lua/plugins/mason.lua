local utils = require("utils")

return {
  {
    "mason-org/mason.nvim",
    enabled = not utils.is_nixos,
  },
  {
    "mason-org/mason-lspconfig.nvim",
    enabled = not utils.is_nixos,
  },
}
