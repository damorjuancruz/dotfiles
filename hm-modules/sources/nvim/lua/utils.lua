local M = {}

-- Detect NixOS from env
M.is_nixos = os.getenv("NVIM_IS_NIXOS") == "1"

return M
