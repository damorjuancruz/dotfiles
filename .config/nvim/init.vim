source ~/.vimrc

set number

set tabstop=2
set shiftwidth=2
set expandtab

" vim-plug
call plug#begin()
  Plug 'nvim-lualine/lualine.nvim'
  Plug 'kyazdani42/nvim-web-devicons'
  Plug 'drewtempelmeyer/palenight.vim'
  Plug 'glacambre/firenvim', { 'do': { _ -> firenvim#install(0) } }
call plug#end()

" Theming
if (has("termguicolors"))
  set termguicolors
  set background=dark
  colorscheme palenight
endif

set noshowmode " hide the mode as it's already shown by lualine
let &fcs='eob: ' " hide the ~ on empty lines

lua << END
require('lualine').setup {
  options = {
    theme = "palenight",
    component_separators = '|',
    section_separators = { left = '', right = '' },
  },
  sections = {
    lualine_a = {
      { 'mode', separator = { left = '' }, right_padding = 2 },
    },
    lualine_b = { 
      { 'filename', path = 3 },
      'branch'
    },
    lualine_c = {},
    lualine_x = {},
    lualine_y = { 'filetype', 'progress' },
    lualine_z = {
      { 'location', separator = { right = '' }, left_padding = 2 },
    },
  },
  inactive_sections = {
    lualine_a = { 'filename' },
    lualine_b = {},
    lualine_c = {},
    lualine_x = {},
    lualine_y = {},
    lualine_z = { 'location' },
  },
  tabline = {},
  extensions = {},
}
END

