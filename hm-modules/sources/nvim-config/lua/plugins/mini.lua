return {
  'echasnovski/mini.nvim',
  version = "*",
  config = function()
    require('mini.ai').setup { n_lines = 500 }
    require('mini.comment').setup()
    -- local hipatterns = require('mini.hipatterns')
    -- hipatterns.setup({
    --   highlighters = {
    --     -- 'FIXME', 'HACK', 'TODO', 'NOTE' are already highlighted for some reason even without these plugin
    --     -- hack  = { pattern = '%f[%w]()HACK()%f[%W]',  group = 'MiniHipatternsHack'  },
    --     -- fixme = { pattern = '%f[%w]()FIXME()%f[%W]', group = 'MiniHipatternsFixme' },
    --     -- todo  = { pattern = '%f[%w]()TODO()%f[%W]',  group = 'MiniHipatternsTodo'  },
    --     -- note  = { pattern = '%f[%w]()NOTE()%f[%W]',  group = 'MiniHipatternsNote'  },
    --
    --     -- Highlight hex color strings (`#rrggbb`) using that color
    --     hex_color = hipatterns.gen_highlighter.hex_color(),
    --   },
    -- })
    require('mini.move').setup()
    require('mini.pairs').setup()
    require('mini.splitjoin').setup()
    require('mini.surround').setup()
    require('mini.jump').setup({
      delay = {
        idle_stop = 0, -- Disable repeat jump by pressing f, F, t, T again
      },
    })
    -- require('mini.sessions').setup({
    --   autoread = true,
    --   file = '',
    -- })
  end,
}
