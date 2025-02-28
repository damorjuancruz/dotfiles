-- Set highlight on search, but clear on pressing <Esc> in normal mode
vim.opt.hlsearch = true
vim.keymap.set('n', '<Esc>', '<cmd>nohlsearch<CR>')

-- Diagnostic keymaps
vim.keymap.set('n', '<leader>q', vim.diagnostic.setloclist, { desc = 'Open diagnostic [Q]uickfix list' })

-- Disable arrow keys in normal mode
vim.keymap.set('n', '<left>', '<cmd>echo "Use h to move!!"<CR>')
vim.keymap.set('n', '<right>', '<cmd>echo "Use l to move!!"<CR>')
vim.keymap.set('n', '<up>', '<cmd>echo "Use k to move!!"<CR>')
vim.keymap.set('n', '<down>', '<cmd>echo "Use j to move!!"<CR>')

--  Use CTRL+<hjkl> to switch between windows
vim.keymap.set('n', '<C-h>', '<C-w><C-h>', { desc = 'Move focus to the left window' })
vim.keymap.set('n', '<C-l>', '<C-w><C-l>', { desc = 'Move focus to the right window' })
vim.keymap.set('n', '<C-j>', '<C-w><C-j>', { desc = 'Move focus to the lower window' })
vim.keymap.set('n', '<C-k>', '<C-w><C-k>', { desc = 'Move focus to the upper window' })

-- save
vim.keymap.set('n', '<leader>w', '<cmd>w<cr>')

-- keep cursor in the middle when scrolling half page or to the end of the file
vim.keymap.set("n", "<C-d>", "<C-d>zz")
vim.keymap.set("n", "<C-u>", "<C-u>zz")
vim.keymap.set("n", "G", "Gzz")

-- keep cursor in the middle when searching
vim.keymap.set("n", "n", "nzzzv")
vim.keymap.set("n", "N", "Nzzzv")

-- paste without replacing clipboard
vim.keymap.set("x", "<leader>p", "\"_dP")

-- delete without replacing clipboard
vim.keymap.set("n", "<leader>d", "\"_d")
vim.keymap.set("v", "<leader>d", "\"_d")

-- change all ocurrencies
vim.keymap.set("n", "<leader>s", [[:%s/\<<C-r><C-w>\>/<C-r><C-w>/gI<Left><Left><Left>]])

-- pressing space alone does nothing
vim.keymap.set({ 'n', 'v' }, '<Space>', '<Nop>', { silent = true })

-- remap for dealing with word wrap
vim.keymap.set({ 'n', 'x' }, 'j', [[v:count == 0 ? 'gj' : 'j']], { expr = true })
vim.keymap.set({ 'n', 'x' }, 'k', [[v:count == 0 ? 'gk' : 'k']], { expr = true })

-- Add empty lines before and after cursor line supporting dot-repeat
vim.g.put_empty_line = function(put_above)
  if type(put_above) == 'boolean' then
    vim.o.operatorfunc = 'v:lua.vim.g.put_empty_line'
    vim.g.cache_empty_line = { put_above = put_above }
    return 'g@l'
  end

  local target_line = vim.fn.line('.') - (vim.g.cache_empty_line.put_above and 1 or 0)
  vim.fn.append(target_line, vim.fn['repeat']({ '' }, vim.v.count1))
end

vim.keymap.set('n', 'gO', 'v:lua.vim.g.put_empty_line(v:true)',  { expr = true, desc = 'Put empty line above' })
vim.keymap.set('n', 'go', 'v:lua.vim.g.put_empty_line(v:false)', { expr = true, desc = 'Put empty line below' })

-- Move with alt
vim.keymap.set('c', '<M-h>', '<Left>',  { silent = false, desc = 'Left' })
vim.keymap.set('c', '<M-l>', '<Right>', { silent = false, desc = 'Right' })

vim.keymap.set('i', '<M-h>', '<Left>',  { noremap = false, desc = 'Left' })
vim.keymap.set('i', '<M-j>', '<Down>',  { noremap = false, desc = 'Down' })
vim.keymap.set('i', '<M-k>', '<Up>',    { noremap = false, desc = 'Up' })
vim.keymap.set('i', '<M-l>', '<Right>', { noremap = false, desc = 'Right' })

vim.keymap.set('t', '<M-h>', '<Left>',  { desc = 'Left' })
vim.keymap.set('t', '<M-j>', '<Down>',  { desc = 'Down' })
vim.keymap.set('t', '<M-k>', '<Up>',    { desc = 'Up' })
vim.keymap.set('t', '<M-l>', '<Right>', { desc = 'Right' })

-- Highlight when yanking (copying) text
vim.api.nvim_create_autocmd('TextYankPost', {
  desc = 'Highlight when yanking (copying) text',
  group = vim.api.nvim_create_augroup('kickstart-highlight-yank', { clear = true }),
  callback = function()
    vim.highlight.on_yank()
  end,
})
