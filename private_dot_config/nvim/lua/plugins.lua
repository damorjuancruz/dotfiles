local ensure_packer = function()
  local fn = vim.fn
  local install_path = fn.stdpath('data') .. '/site/pack/packer/start/packer.nvim'
  if fn.empty(fn.glob(install_path)) > 0 then
    fn.system({ 'git', 'clone', '--depth', '1', 'https://github.com/wbthomason/packer.nvim', install_path })
    vim.cmd [[packadd packer.nvim]]
    return true
  end
  return false
end

ensure_packer()

-- autocommand that reloads neovim whenever you save the plugins.lua file
vim.cmd [[ augroup packer_user_config
    autocmd!
    autocmd BufWritePost plugins.lua source <afile> | PackerSync
  augroup end
]]

return require('packer').startup(function(use)
  -- Packer can manage itself
  use 'wbthomason/packer.nvim'


  use {
    'nvim-telescope/telescope.nvim', tag = '0.1.3',
    requires = {
      { 'nvim-lua/plenary.nvim' },
      { "debugloop/telescope-undo.nvim" },
      { 'nvim-telescope/telescope-ui-select.nvim' },
    }
  }

  use { "catppuccin/nvim", as = "catppuccin" }

  use('nvim-treesitter/nvim-treesitter', { run = ':TSUpdate' })
  use 'nvim-treesitter/playground'
  use 'nvim-treesitter/nvim-treesitter-context'
  use {
    "luckasRanarison/tree-sitter-hyprlang",
    requires = { "nvim-treesitter/nvim-treesitter" },
  }

  use {
    'VonHeikemen/lsp-zero.nvim',
    branch = 'v3.x',
    requires = {
      -- LSP Support
      { 'neovim/nvim-lspconfig' }, -- Required
      {                            -- Optional
        'williamboman/mason.nvim',
        run = function()
          ---@diagnostic disable-next-line: param-type-mismatch
          pcall(vim.cmd, 'MasonUpdate')
        end,
      },
      { 'williamboman/mason-lspconfig.nvim' }, -- Optional

      -- Autocompletion
      { 'hrsh7th/nvim-cmp' },     -- Required
      { 'hrsh7th/cmp-nvim-lsp' }, -- Required
      { 'hrsh7th/cmp-nvim-lsp-signature-help' },
      { 'hrsh7th/cmp-cmdline' },
      { 'hrsh7th/cmp-buffer' },
      { 'hrsh7th/cmp-calc' },
      { 'FelipeLema/cmp-async-path' },
      {
        "mtoohey31/cmp-fish",
        ft = "fish"
      },
      { 'onsails/lspkind-nvim' },
      { 'L3MON4D3/LuaSnip' }, -- Required
    }
  }

  use 'windwp/nvim-ts-autotag'

  use {
    'nvim-lualine/lualine.nvim',
    requires = { 'nvim-tree/nvim-web-devicons', opt = true }
  }

  use "nvim-tree/nvim-web-devicons"

  vim.cmd([[ let g:neo_tree_remove_legacy_commands = 1 ]])

  use {
    "nvim-neo-tree/neo-tree.nvim",
    branch = "v2.x",
    requires = {
      "nvim-lua/plenary.nvim",
      "nvim-tree/nvim-web-devicons", -- not strictly required, but recommended
      "MunifTanjim/nui.nvim",
    }
  }

  use {
    'lewis6991/gitsigns.nvim',
    -- tag = 'release' -- To use the latest release (do not use this if you run Neovim nightly or dev builds!)
  }

  use "lukas-reineke/indent-blankline.nvim"

  use { 'echasnovski/mini.nvim', branch = 'stable' }

  use 'nacro90/numb.nvim'

  use 'christoomey/vim-tmux-navigator'

  use "akinsho/toggleterm.nvim"

  use({
    "epwalsh/obsidian.nvim",
    tag = "*", -- recommended, use latest release instead of latest commit
    requires = {
      "nvim-lua/plenary.nvim",
    },
  })
end)
