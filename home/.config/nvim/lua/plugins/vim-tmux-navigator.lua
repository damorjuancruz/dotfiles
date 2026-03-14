return {
  "christoomey/vim-tmux-navigator",
  cmd = {
    "TmuxNavigateLeft",
    "TmuxNavigateDown",
    "TmuxNavigateUp",
    "TmuxNavigateRight",
    "TmuxNavigatePrevious",
    "TmuxNavigatorProcessList",
  },
  keys = {
    { "<c-h>",  "<cmd><C-U>TmuxNavigateLeft<cr>",     desc = "tmux navigate left" },
    { "<c-j>",  "<cmd><C-U>TmuxNavigateDown<cr>",     desc = "tmux navigate down" },
    { "<c-k>",  "<cmd><C-U>TmuxNavigateUp<cr>",       desc = "tmux navigate up" },
    { "<c-l>",  "<cmd><C-U>TmuxNavigateRight<cr>",    desc = "tmux navigate right" },
    { "<c-\\>", "<cmd><C-U>TmuxNavigatePrevious<cr>", desc = "tmux navigate previous" },
  },
}
