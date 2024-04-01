local parser_config = require("nvim-treesitter.parsers").get_parser_configs()

parser_config.hypr = {
  install_info = {
    url = "https://github.com/luckasRanarison/tree-sitter-hyprlang",
    files = { "src/parser.c" },
    branch = "master",
  },
  filetype = "hypr",
}

require 'nvim-treesitter.configs'.setup {
  autotag = {
    enable = true,
  },

  -- A list of parser names, or "all"
  ensure_installed = {
    'bash',
    'comment',
    'cpp',
    'css',
    'diff',
    'dockerfile',
    'fish',
    'gitignore',
    'html',
    'json',
    "javascript",
    "markdown",
    "markdown_inline",
    'prisma',
    "python",
    'racket',
    'scss',
    'sql',
    'svelte',
    'vue',
    'tsx',
    "typescript",
    'yaml',
    'php',
    'hypr',
    "c", "lua", "vim", "vimdoc", "query" -- (this five parsers should always be installed)
  },

  -- Install parsers synchronously (only applied to `ensure_installed`)
  sync_install = true,

  -- Automatically install missing parsers when entering buffer
  -- Recommendation: set to false if you don't have `tree-sitter` CLI installed locally
  auto_install = false,

  highlight = {
    enable = true,
    additional_vim_regex_highlighting = false,
  },
}
