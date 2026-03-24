# ZSH Dependencies
RemovePackage cachyos-zsh-config
RemovePackage oh-my-zsh-git
RemovePackage zsh-autosuggestions
RemovePackage zsh-completions
RemovePackage zsh-history-substring-search
RemovePackage zsh-syntax-highlighting
RemovePackage zsh-theme-powerlevel10k
AddPackage zsh       # A very advanced and programmable command interpreter (shell) for UNIX
AddPackage starship  # The cross-shell prompt for astronauts
AddPackage bat       # Cat clone with syntax highlighting and git integration
AddPackage eza       # A modern replacement for ls (community fork of exa)
AddPackage git       # the fast distributed version control system
AddPackage fzf       # Command-line fuzzy finder
AddPackage trash-cli # Command line trashcan (recycle bin) interface
AddPackage zoxide    # A smarter cd command for your terminal
AddPackage vivid     # LS_COLORS manager with multiple themes

# Neovim Dependencies
RemovePackage vim
RemovePackage micro
RemovePackage cachyos-micro-settings
AddPackage neovim          # Fork of Vim aiming to improve user experience, plugins, and GUIs
AddPackage clang           # C language family frontend for LLVM
AddPackage fzf             # Command-line fuzzy finder
AddPackage curl            # command line tool and library for transferring data with URLs
AddPackage git             # the fast distributed version control system
AddPackage lazygit         # Simple terminal UI for git commands
AddPackage lua             # Powerful lightweight programming language designed for extending applications
AddPackage luarocks        # Deployment and management system for Lua modules
AddPackage ripgrep         # A search tool that combines the usability of ag with the raw speed of grep
AddPackage fd              # Simple, fast and user-friendly alternative to find
AddPackage tree-sitter-cli # CLI tool for developing, testing, and using Tree-sitter parsers

# Utils
AddPackage --foreign aconfmgr-git # A configuration manager for Arch Linux
AddPackage stow                   # Manage installation of multiple softwares in the same directory tree
AddPackage paru                   # Feature packed AUR helper
AddPackage git                    # the fast distributed version control system
AddPackage btop                   # A monitor of system resources, bpytop ported to C++
AddPackage fastfetch              # A feature-rich and performance oriented neofetch like system information tool
AddPackage curl                   # command line tool and library for transferring data with URLs
AddPackage fnm                    # Fast and simple Node.js version manager, built with Rust
AddPackage xdg-user-dirs          # Manage user directories like ~/Desktop and ~/Music
