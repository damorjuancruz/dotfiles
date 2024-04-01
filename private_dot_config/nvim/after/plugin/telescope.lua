local actions = require('telescope.actions')

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
      n = {
        ['dd'] = require('telescope.actions').delete_buffer
      }
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

vim.keymap.set('n', '<leader>?', builtin.keymaps, {})
vim.keymap.set('n', '<leader>fb', builtin.buffers, {})
vim.keymap.set('n', '<leader>fr', builtin.resume, {})
vim.keymap.set('n', '<leader>fg', builtin.live_grep, {})
vim.keymap.set('n', '<leader>/', builtin.current_buffer_fuzzy_find, {})
vim.keymap.set("n", "<leader>u", require("telescope").extensions.undo.undo)

require('telescope').load_extension('ui-select')

local cdPicker = function(name, cmd)
  local results = require("telescope.utils").get_os_command_output(cmd)

  -- local results_with_icons = {}
  -- for k, v in ipairs(results) do
  --   print(v)
  --   results_with_icons[k] = ' ' .. v
  -- end

  require("telescope.pickers").new({}, {
    prompt_title = name,
    finder = require("telescope.finders").new_table({ results = results }),
    previewer = require("telescope.previewers").vim_buffer_cat.new({}),
    sorter = require("telescope.sorters").get_fuzzy_file(),
    attach_mappings = function(prompt_bufnr)
      require("telescope.actions.set").select:replace(function(_)
        local entry = require("telescope.actions.state").get_selected_entry()
        actions.close(prompt_bufnr)
        local dir = require("telescope.from_entry").path(entry)
        vim.api.nvim_set_current_dir(dir)
      end)
      return true
    end,
  }):find()
end

local cd = function(paths)
  paths = paths or "."
  cdPicker("Change Working Directory", {
    vim.o.shell,
    "-c",
    "fd . " .. paths .. " -td -tl -H --base-directory $HOME --max-depth 1",
  })
end

vim.keymap.set("n", "<leader>cd", function() cd('$HOME $HOME/code $HOME/code/fiduxion $HOME/.config $HOME/documents') end,
  {})
