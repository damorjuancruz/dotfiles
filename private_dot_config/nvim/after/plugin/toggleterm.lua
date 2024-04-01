require('toggleterm').setup {
  size = function(term)
    if term.direction == "horizontal" then
      return 20
    elseif term.direction == "vertical" then
      return 60
    end
  end,
  shade_terminals = true,
  shading_factor = '-10',
  shell = '/bin/fish',
  terminal_mappings = false
}

vim.keymap.set('n', '<C-\\>', function()
  vim.cmd(vim.v.count .. "ToggleTerm direction=vertical")
end)
vim.keymap.set('n', '<A-\\>', function()
  vim.cmd(vim.v.count .. "ToggleTerm direction=horizontal")
end)
vim.keymap.set('n', '<C-f>', function()
  vim.cmd(vim.v.count .. "ToggleTerm direction=float")
end)

function _G.set_terminal_keymaps()
  local opts = { buffer = 0 }
  vim.keymap.set('t', '<C-\\>', "<Cmd>ToggleTerm<CR>")
  vim.keymap.set('t', '<A-\\>', "<Cmd>ToggleTerm<CR>")
  vim.keymap.set('t', '<C-f>', "<Cmd>ToggleTerm<CR>")
  vim.keymap.set('t', 'jk', [[<C-\><C-n>]], opts)
  vim.keymap.set('t', '<C-h>', [[<Cmd>wincmd h<CR>]], opts)
  vim.keymap.set('t', '<C-j>', [[<Cmd>wincmd j<CR>]], opts)
  vim.keymap.set('t', '<C-k>', [[<Cmd>wincmd k<CR>]], opts)
  vim.keymap.set('t', '<C-l>', [[<Cmd>wincmd l<CR>]], opts)
end

-- if you only want these mappings for toggle term use term://*toggleterm#* instead
vim.cmd('autocmd! TermOpen term://*toggleterm#* lua set_terminal_keymaps()')
