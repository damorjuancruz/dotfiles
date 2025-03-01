vim.opt.number = true
vim.opt.relativenumber = true

-- Enable mouse mode, can be useful for resizing splits for example!
vim.opt.mouse = 'a'

-- Don't show the mode, since it's already in the status line
vim.opt.showmode = false

-- Sync clipboard between OS and Neovim.
vim.opt.clipboard = 'unnamedplus'

-- Enable break indent
vim.opt.breakindent = true
vim.opt.wrap = true
-- character to show at the start of a line that has been wrapped
vim.opt.showbreak = '↳'
vim.opt.linebreak = true

-- Save undo history
vim.opt.undofile = true
vim.opt.swapfile = false -- no swap file
vim.opt.backup = false -- no backup file

-- Case-insensitive searching UNLESS \C or one or more capital letters in the search term
vim.opt.ignorecase = true
vim.opt.smartcase = true
-- search as you type
vim.opt.incsearch = true
-- Infer letter cases for a richer built-in keyword completion
vim.opt.infercase = true -- TODO test

-- Keep signcolumn on by default
vim.opt.signcolumn = 'yes'

-- Decrease update time
vim.opt.updatetime = 50

-- Configure how new splits should be opened
vim.opt.splitright = true
vim.opt.splitbelow = true

-- Sets how neovim will display certain whitespace characters in the editor.
vim.opt.list = true
vim.opt.listchars = { tab = '» ', trail = '·', nbsp = '␣' }

-- Preview substitutions live, as you type!
vim.opt.inccommand = 'split'

-- Show which line your cursor is on
vim.opt.cursorline = true

-- Minimal number of screen lines to keep above and below the cursor.
vim.opt.scrolloff = 5

vim.opt.termguicolors = true  -- 24-bit colors

-- tab size
vim.opt.tabstop = 2
vim.opt.softtabstop = 2
-- spaces added when entering a new block (e.g.: if (...) { <enter>)
vim.opt.shiftwidth = 2
-- use spaces
vim.opt.expandtab = true

vim.opt.autoindent = true
vim.opt.smartindent = true
vim.opt.smarttab = true

-- limit amount of options in the completion menu (creates scroll)
vim.opt.pumheight = 10
-- TODO test
vim.opt.pumblend = 10 -- Make builtin completion menus slightly transparent
vim.opt.winblend = 10 -- Make floating windows slightly transparent

-- window title
vim.opt.title = true

-- folds
vim.opt.fillchars = { fold = " " }
vim.opt.foldmethod = "indent"
vim.opt.foldenable = false
vim.opt.foldlevel = 99
-- enable markdown folding
vim.g.markdown_folding = 1

vim.opt.guifont = 'FiraCode Nerd Font:h11'

vim.opt.conceallevel = 2 -- obsidia.nvim's additional highlighting
