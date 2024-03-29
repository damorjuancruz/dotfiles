local actions = require('telescope.actions')

local fb_actions = require "telescope".extensions.file_browser.actions
require('telescope').setup({
  extensions = {
    undo = {
      mappings = {
        i = {
          ["<cr>"] = require("telescope-undo.actions").restore,
        },
        n = {
          ["<cr>"] = require("telescope-undo.actions").restore,
        },
      },
    },
    file_browser = {
      grouped = true,
      hidden = true,
      mappings = {
        ['i'] = {
          ["<C-t>"] = function(prompt_bufnr)
            fb_actions.change_cwd(prompt_bufnr)
            actions.close(prompt_bufnr)
          end,
        },
        ['n'] = {
          ["t"] = function(prompt_bufnr)
            fb_actions.change_cwd(prompt_bufnr)
            actions.close(prompt_bufnr)
          end,
        },
      },
    },
  },
  defaults = {
    file_ignore_patterns = {
      'node_modules', '.git', '.next', 'dist' -- in addition to .gitignore
    },
    sorting_strategy = 'ascending',
    layout_strategy = 'center',
    layout_config = {
      center = {
        anchor = "N",
        width = 80,
      },
    },
    mappings = {
      i = {
        ["<C-j>"] = actions.move_selection_next,
        ["<C-k>"] = actions.move_selection_previous,
      },
    },
  },
})

local builtin = require('telescope.builtin')

vim.keymap.set('n', '<leader>ff', function() -- respects .gitignore
  builtin.find_files({
    hidden = true,
  })
end, {})
vim.keymap.set('n', '<leader>fi', function() -- doesn't respect .gitignore
  builtin.find_files({
    hidden = true,
    no_ignore = true,
    no_ignore_parent = true,
  })
end, {})
vim.keymap.set('n', '<leader><leader>f', ":Telescope file_browser<CR>", {})

vim.keymap.set('n', '<leader>?', builtin.keymaps, {})
vim.keymap.set('n', '<leader>fb', builtin.buffers, {})
vim.keymap.set('n', '<leader>fr', builtin.resume, {})
vim.keymap.set('n', '<leader>fg', builtin.live_grep, {})
vim.keymap.set('n', '<leader>f/', builtin.current_buffer_fuzzy_find, {})
vim.keymap.set("n", "<leader>u", require("telescope").extensions.undo.undo)

require("telescope").load_extension("file_browser")
require('telescope').load_extension('ui-select')
