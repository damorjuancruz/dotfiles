require('mini.ai').setup()
-- local animate = require('mini.animate')
-- local linearAnimation100ms = animate.gen_timing.linear({ duration = 100, unit = 'total', })
-- animate.setup({
--   cursor = { enabled = true, timing = linearAnimation100ms, },
--   scroll = { enabled = true, timing = linearAnimation100ms, },
--   resize = { enabled = true, timing = linearAnimation100ms, },
--   open = { enabled = true, timing = linearAnimation100ms, },
--   close = { enabled = true, timing = linearAnimation100ms, },
-- })
-- require('mini.basics').setup() -- TODO: steal settings from here
require('mini.comment').setup()
-- require('mini.cursorword').setup()
local hipatterns = require('mini.hipatterns')
hipatterns.setup({
  highlighters = {
    -- 'FIXME', 'HACK', 'TODO', 'NOTE' are already highlighted for some reason even without these plugin
    -- hack  = { pattern = '%f[%w]()HACK()%f[%W]',  group = 'MiniHipatternsHack'  },
    -- fixme = { pattern = '%f[%w]()FIXME()%f[%W]', group = 'MiniHipatternsFixme' },
    -- todo  = { pattern = '%f[%w]()TODO()%f[%W]',  group = 'MiniHipatternsTodo'  },
    -- note  = { pattern = '%f[%w]()NOTE()%f[%W]',  group = 'MiniHipatternsNote'  },

    -- Highlight hex color strings (`#rrggbb`) using that color
    hex_color = hipatterns.gen_highlighter.hex_color(),
  },
})
require('mini.move').setup()
require('mini.pairs').setup()
require('mini.splitjoin').setup()
require('mini.sessions').setup() -- FIXME
require('mini.starter').setup()
require('mini.surround').setup()
