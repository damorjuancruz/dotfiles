return {
  'catppuccin/nvim',
  name = 'catppuccin',
  version = '*',
  priority = 1000, -- Make sure to load this before all the other start plugins.
  opts = {
    flavour = "mocha",
    show_end_of_buffer = false, -- shows the '~' characters after the end of buffers
    integrations = {
      cmp = true,
      gitsigns = true,
      neotree = true,
      telescope = true,
      treesitter = true,
      mini = true,
      mason = true,
      native_lsp = {
        enabled = true,
      },
    },
  },
  init = function()
    vim.cmd.colorscheme 'catppuccin'
  end,
}
