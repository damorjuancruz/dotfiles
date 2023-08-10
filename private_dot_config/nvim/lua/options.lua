vim.opt.termguicolors = true  -- 24-bit colors
vim.opt.nu = true             -- line numbers
vim.opt.relativenumber = true -- relative line numbers
vim.opt.cursorline = true     -- highlight current line

vim.opt.tabstop = 2           -- tab size
vim.opt.softtabstop = 2
vim.opt.shiftwidth = 2        -- spaces added when entering a new block (e.g.: if (...) { <enter>)
vim.opt.expandtab = true      -- use spaces
vim.opt.autoindent = true
vim.opt.smartindent = true
vim.opt.smarttab = true

vim.opt.wrap = true        -- line wrap
vim.opt.breakindent = true -- keep indentation when wrapped
vim.opt.showbreak = '↳'  -- character to show at the start of a line that has been wrapped

vim.opt.swapfile = false   -- no swap file
vim.opt.backup = false     -- no backup file
vim.opt.undofile = true    -- persist undo history between sessions

vim.opt.hlsearch = false   -- don't highlight search results
vim.opt.incsearch = true   -- search as you type
-- case-insensitive search unless capital letters are present
vim.opt.ignorecase = true
vim.opt.smartcase = true

vim.opt.scrolloff = 8      -- padding when scrolling
vim.opt.signcolumn = "yes" -- allow showing git status, breakpoints, etc

vim.opt.updatetime = 50

vim.opt.clipboard:append { 'unnamedplus' } -- use system clipboard. requires wl-clipboard/xclip

-- create new splits intuitively
vim.opt.splitbelow = true
vim.opt.splitright = true

vim.opt.mouse = "a"          -- mouse support for all modes

vim.opt.pumheight = 10       -- limit amount of options in the completion menu (creates scroll)

vim.opt.title = true         -- window title

vim.opt.inccommand = "split" -- preview results of commands in a split


-- folds
vim.opt.fillchars = { fold = " " }
vim.opt.foldmethod = "indent"
vim.opt.foldenable = false
vim.opt.foldlevel = 99
vim.g.markdown_folding = 1 -- enable markdown folding
