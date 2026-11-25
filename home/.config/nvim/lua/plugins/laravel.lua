-- PHP y Laravel, alineado con la config de VS Code y Zed de los proyectos Laravel:
-- intelephense como LSP sin formateo propio, Pint para PHP y Blade, Larastan como linter.
-- `vim.g.lazyvim_php_lsp = "intelephense"` está en lua/config/options.lua porque el extra lang.php lo lee al cargar.

-- Directorio más cercano, subiendo desde `path`, que contiene alguno de `markers` (admiten rutas como "vendor/bin/pint").
local function root_with(path, markers)
  local found = vim.fs.find(markers, { path = vim.fs.dirname(path), upward = true })[1]
  return found and vim.fs.dirname(found) or nil
end

local function pint_root(path)
  local bin = vim.fs.find("vendor/bin/pint", { path = vim.fs.dirname(path), upward = true })[1]
  return bin and vim.fs.dirname(vim.fs.dirname(vim.fs.dirname(bin))) or nil
end

local function phpstan_root(path)
  local root = root_with(path, { "phpstan.neon", "phpstan.neon.dist" })
  return root and vim.uv.fs_stat(root .. "/vendor/bin/phpstan") and root or nil
end

return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = { ensure_installed = { "php", "blade" } },
  },

  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        intelephense = {
          settings = {
            intelephense = {
              environment = { phpVersion = "8.5.0" },
              format = { enable = false },
              -- Reemplaza el default de intelephense ({ "**/vendor/**": ["*"] }), por eso repite vendor.
              -- Pest declara $this como TestCall (sin __set). PHPStan, que usan tests/PHPStan y tests/Rector, viene
              -- en un .phar que intelephense no indexa. Larastan cubre esos chequeos.
              diagnostics = {
                exclude = {
                  ["**/vendor/**"] = { "*" },
                  ["**/tests/{Feature,Unit}/**"] = { "P1014" },
                  ["**/tests/{PHPStan,Rector}/**"] = { "P1006", "P1009" },
                },
              },
              -- Los excludes default de intelephense, más storage y bootstrap/cache.
              files = {
                exclude = {
                  "**/.git/**",
                  "**/.svn/**",
                  "**/.hg/**",
                  "**/CVS/**",
                  "**/.DS_Store/**",
                  "**/node_modules/**",
                  "**/bower_components/**",
                  "**/vendor/**/{Tests,tests}/**",
                  "**/.history/**",
                  "**/vendor/**/vendor/**",
                  "**/storage/**",
                  "**/bootstrap/cache/**",
                },
              },
            },
          },
        },
      },
    },
  },

  -- Pint y PHPStan vienen del vendor de cada proyecto; mason no instala phpcs ni php-cs-fixer.
  {
    "mason-org/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = vim.tbl_filter(function(pkg)
        return pkg ~= "phpcs" and pkg ~= "php-cs-fixer"
      end, opts.ensure_installed or {})
    end,
  },

  {
    "stevearc/conform.nvim",
    opts = {
      formatters_by_ft = {
        php = { "pint" },
        blade = { "pint" },
      },
      formatters = {
        -- Por stdin: con la ruta del archivo como argumento, Pint ignora el `exclude` de pint.json.
        pint = {
          -- conform evalúa command aunque condition dé false, así que no puede fallar fuera de un proyecto con Pint.
          command = function(_, ctx)
            local root = pint_root(ctx.filename)
            return root and root .. "/vendor/bin/pint" or "pint"
          end,
          -- conform solo reemplaza $FILENAME cuando es el argumento entero, no dentro de "--stdin-filename=...".
          args = function(_, ctx)
            return { "-", "--stdin-filename=" .. ctx.filename }
          end,
          stdin = true,
          cwd = function(_, ctx)
            return pint_root(ctx.filename)
          end,
          require_cwd = true,
          condition = function(_, ctx)
            return pint_root(ctx.filename) ~= nil
          end,
        },
      },
    },
  },

  {
    "mfussenegger/nvim-lint",
    opts = {
      linters_by_ft = {
        php = { "phpstan" },
      },
      linters = {
        -- Larastan con el phpstan del proyecto, desde su raíz: Larastan arranca la app con bootstrap/app.php del cwd.
        phpstan = {
          cmd = function()
            local root = phpstan_root(vim.api.nvim_buf_get_name(0))
            return root and root .. "/vendor/bin/phpstan" or "phpstan"
          end,
          args = { "analyse", "--error-format=json", "--no-progress", "--memory-limit=1G" },
          condition = function(ctx)
            local root = phpstan_root(ctx.filename)
            -- nvim-lint no acepta cwd dinámico; LazyVim evalúa condition justo antes de lanzar el linter.
            require("lint").linters.phpstan.cwd = root
            return root ~= nil
          end,
        },
        -- Solo en proyectos con su propia config; los demás formatean Markdown con Prettier.
        ["markdownlint-cli2"] = {
          condition = function(ctx)
            return vim.fs.find(function(name)
              return name:match("^%.markdownlint") ~= nil
            end, { path = ctx.dirname, upward = true })[1] ~= nil
          end,
        },
      },
    },
  },
}
