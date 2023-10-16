local lsp_zero = require('lsp-zero')

require('mason').setup({})
require('mason-lspconfig').setup({
  ensure_installed = {
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
  },
  handlers = {
    lsp_zero.default_setup,
    lua_ls = function()
      local lua_opts = lsp_zero.nvim_lua_ls()
      require('lspconfig').lua_ls.setup(lua_opts)
    end,
  }
})

local telescope = require('telescope.builtin')
lsp_zero.on_attach(function(_, bufnr)
  lsp_zero.default_keymaps({
    buffer = bufnr,
    exclude = { 'gr', 'gd' }
  })
  lsp_zero.buffer_autoformat()

  local opts = { buffer = bufnr }

  vim.keymap.set("n", "gr", telescope.lsp_references, opts)
  vim.keymap.set("n", "gd", telescope.lsp_definitions, opts)
  vim.keymap.set("n", "<leader>r", vim.lsp.buf.rename, opts)
  vim.keymap.set("n", "<leader>f", vim.lsp.buf.format, opts)
  vim.keymap.set("n", "<leader>ca", vim.lsp.buf.code_action, opts)
end)

require('lspconfig').lua_ls.setup(lsp_zero.nvim_lua_ls())
require('lspconfig').volar.setup({
  filetypes = { 'typescript', 'javascript', 'vue', 'json' }
})
vim.api.nvim_create_autocmd("LspAttach", {
  callback = function(args)
    local client = vim.lsp.get_client_by_id(args.data.client_id)

    if (client.name == 'tsserver') then
      local volarAttached = #(
        vim.lsp.get_active_clients({
          bufnr = args.buf,
          name = 'volar'
        })
      ) > 0
      if (volarAttached) then
        client.stop()
        print('tsserver stopped')
      end
    else
      if (client.name == 'volar') then
        local tsserver_clients = vim.lsp.get_active_clients({
          bufnr = args.buf,
          name = 'tsserver'
        })
        local tsserverAttached = #tsserver_clients > 0

        if (tsserverAttached) then
          tsserver_clients[1].stop()
          print('tsserver stopped')
        end
      end
    end
  end,
})

lsp_zero.setup()

local cmp = require('cmp')
local cmp_select_opts = { behavior = cmp.SelectBehavior.Select }
local lspkind = require('lspkind')

cmp.setup({
  sources = {
    { name = 'nvim_lsp' },
    { name = 'fish' },
    { name = 'nvim_lsp_signature_help' },
    { name = 'luasnip' },
    { name = 'buffer' },
    { name = 'async_path' },
    { name = 'calc' },
  },
  formatting = {
    format = lspkind.cmp_format({
      mode = 'symbol_text',  -- show only symbol annotations
      maxwidth = 50,         -- prevent the popup from showing more than provided characters (e.g 50 will not show more than 50 characters)

      ellipsis_char = '...', -- when popup menu exceed maxwidth, the truncated part would show ellipsis_char instead (must define maxwidth first)
    })
  },
  mapping = cmp.mapping.preset.insert({
    ['<C-k>'] = cmp.mapping(cmp.mapping.select_prev_item(cmp_select_opts), { 'i', 'c' }),
    ['<C-j>'] = cmp.mapping(cmp.mapping.select_next_item(cmp_select_opts), { 'i', 'c' }),
    ['<Tab>'] = cmp.mapping(cmp.mapping.confirm(), { 'i', 'c' }),
    ['<C-Space>'] = cmp.mapping(cmp.mapping.complete(), { 'i', 'c' }),
    ['<C-e>'] = cmp.mapping(cmp.mapping.abort(), { 'i', 'c' }),
    ['<C-u>'] = cmp.mapping.scroll_docs(-2),
    ['<C-d>'] = cmp.mapping.scroll_docs(2),
  }),
  preselect = 'item',
  completion = {
    completeopt = 'menu,menuone,noinsert'
  },
})

-- `/` cmdline setup.
cmp.setup.cmdline({ '/', '?' }, {
  sources = {
    { name = 'buffer' }
  }
})

-- `:` cmdline setup.
cmp.setup.cmdline(':', {
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
