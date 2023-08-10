local lsp = require('lsp-zero').preset({ name = 'recommended' })

lsp.ensure_installed({
  'bashls',
  'clangd',
  'cssls',
  'dockerls',
  'docker_compose_language_service',
  'eslint',
  'grammarly',
  'html',
  'jsonls',
  'tsserver',
  'lua_ls',
  'marksman',
  'prismals',
  'pyright',
  'svelte',
  'tailwindcss',
  'yamlls',
  'sqlls',
  'vimls',
  'volar',
  'intelephense',
  'custom_elements_ls',
})

lsp.on_attach(function(_, bufnr)
  lsp.default_keymaps({ buffer = bufnr })

  local opts = { buffer = bufnr }

  vim.keymap.set("n", "<leader>r", vim.lsp.buf.rename, opts)
  vim.keymap.set("n", "<leader>f", vim.lsp.buf.format, opts)
  vim.keymap.set("n", "<leader>ca", vim.lsp.buf.code_action, opts)
end)

require('lspconfig').lua_ls.setup(lsp.nvim_lua_ls())

lsp.format_on_save({
  servers = {
    ['lua_ls'] = { 'lua' },
    ['clangd'] = { 'c' },
    ['tsserver'] = { 'typescript' },
  }
})

lsp.setup()

local cmp = require('cmp')
local cmp_select_opts = { behavior = cmp.SelectBehavior.Select }
local lspkind = require('lspkind')

cmp.setup({
  formatting = {
    format = lspkind.cmp_format({
      mode = 'symbol_text',  -- show only symbol annotations
      maxwidth = 50,         -- prevent the popup from showing more than provided characters (e.g 50 will not show more than 50 characters)
      ellipsis_char = '...', -- when popup menu exceed maxwidth, the truncated part would show ellipsis_char instead (must define maxwidth first)
    })
  },
  mapping = lsp.defaults.cmp_mappings({
    ['<C-k>'] = cmp.mapping(cmp.mapping.select_prev_item(cmp_select_opts), { 'i', 'c' }),
    ['<C-j>'] = cmp.mapping(cmp.mapping.select_next_item(cmp_select_opts), { 'i', 'c' }),
    ['<Tab>'] = cmp.mapping(cmp.mapping.confirm(), { 'i', 'c' }),
    ['<C-Space>'] = cmp.mapping(cmp.mapping.complete(), { 'i', 'c' }),
    ['<C-e>'] = cmp.mapping(cmp.mapping.abort(), { 'i', 'c' }),
  }),
  preselect = 'item',
  completion = {
    completeopt = 'menu,menuone,noinsert'
  },
})

-- `/` cmdline setup.
cmp.setup.cmdline({ '/', '?' }, {
  -- mapping = cmp.mapping.preset.cmdline(),
  sources = {
    { name = 'buffer' }
  }
})

-- `:` cmdline setup.
cmp.setup.cmdline(':', {
  -- mapping = cmp.mapping.preset.cmdline(),
  sources = cmp.config.sources({
    { name = 'path' }
  }, {
    {
      name = 'cmdline',
      option = {
        ignore_cmds = { 'Man', '!' }
      }
    }
  })
})
