require("obsidian").setup({
  dir = "~/documents/notes",
  notes_subdir = '0-inbox',

  completion = {
    new_notes_location = "notes_subdir",
    min_chars = 0,
  },

  note_id_func = function(title)
    -- Create note IDs in a Zettelkasten format with a timestamp and a suffix. In this case a note with the title 'My new note' will be given an ID that looks like '1657296016-my-new-note', and therefore the file name '1657296016-my-new-note.md'

    local suffix = ""
    if title ~= nil then
      -- If title is given, transform it into valid file name.
      suffix = title:gsub(" ", "-"):gsub("[^A-Za-z0-9-]", ""):lower()
    else
      -- If title is nil, just add 4 random uppercase letters to the suffix.
      for _ = 1, 4 do
        suffix = suffix .. string.char(math.random(65, 90))
      end
    end
    return tostring(os.time()) .. "-" .. suffix
  end,

  follow_url_func = function(url)
    vim.fn.jobstart({ "xdg-open", url })
  end,

  open_app_foreground = true,
})

vim.keymap.set('n', '<leader>of', '<cmd>ObsidianQuickSwitch<CR>', {})
vim.keymap.set('n', '<leader>os', '<cmd>ObsidianSearch<CR>', {})
vim.keymap.set('n', '<leader>ob', '<cmd>ObsidianBacklinks<CR>', {})
vim.keymap.set('n', '<leader>on', ':ObsidianNew ', {})
vim.keymap.set('n', '<leader>or', ':ObsidianRename', {})
vim.keymap.set('n', '<leader>op', '<cmd>ObsidianPasteImg<CR>', {})
