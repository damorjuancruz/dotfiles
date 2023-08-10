require('lualine').setup {
  options = {
    disabled_filetypes = {
      'neo-tree',
      'alpha',
    },
    theme = 'catppuccin',
    component_separators = '·',
    section_separators = '',
  },
  sections = {
    lualine_a = { 'mode', 'selectioncount' },
    lualine_b = { { 'filename', path = 1 }, 'branch', 'diff' },
    lualine_c = {},
    lualine_x = {},
    lualine_y = { 'filetype', 'o:encoding', 'progress' },
    lualine_z = { 'location' },
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

vim.opt.showmode = false
