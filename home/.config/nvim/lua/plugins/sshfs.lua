return {
  "uhs-robert/sshfs.nvim",
  opts = {
    hooks = {
      on_mount = {
        auto_change_to_dir = true,
        auto_run = "none",
      },
    },
  },
}
