# claude-zsh-completions

Zsh tab-completions for the [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI (`v2.1.x`).

Covers all flags, subcommands (`agents`, `auth`, `doctor`, `install`, `mcp`, `plugin`, `setup-token`, `update`), and their nested options — including deep completions for `mcp add`, `plugin install/uninstall/marketplace`, `auth login/status`, and more.

## Install

### Oh My Zsh (recommended)

Clone into your custom plugins directory:

```sh
git clone https://github.com/ivanearisty/claude-zsh-completions.git \
  "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/claude"
```

Then add `claude` to the plugins array in `~/.zshrc`:

```zsh
plugins=(... claude)
```

Reload your shell:

```sh
source ~/.zshrc
```

### Manual

Copy `_claude` to any directory in your `$fpath` and rebuild the completion cache:

```sh
cp _claude /usr/local/share/zsh/site-functions/
autoload -Uz compinit && compinit
```

## What you get

```
$ claude <TAB>
agents       -- List configured agents
auth         -- Manage authentication
doctor       -- Check the health of your Claude Code auto-updater
install      -- Install Claude Code native build
mcp          -- Configure and manage MCP servers
plugin       -- Manage Claude Code plugins
setup-token  -- Set up a long-lived authentication token
update       -- Check for updates and install if available

$ claude --<TAB>
--add-dir          --debug-file       --model          --print
--agent            --effort           --mcp-config     --resume
--brief            --fork-session     --name           --tmux
--worktree         ...

$ claude mcp <TAB>
add                    -- Add an MCP server to Claude Code
add-from-claude-desktop -- Import MCP servers from Claude Desktop
add-json               -- Add an MCP server with a JSON string
get                    -- Get details about an MCP server
list                   -- List configured MCP servers
remove                 -- Remove an MCP server
serve                  -- Start the Claude Code MCP server

$ claude plugin <TAB>
install      -- Install a plugin from available marketplaces
uninstall    -- Uninstall an installed plugin
list         -- List installed plugins
enable       -- Enable a disabled plugin
disable      -- Disable an enabled plugin
update       -- Update a plugin to the latest version
validate     -- Validate a plugin or marketplace manifest
marketplace  -- Manage Claude Code marketplaces
```

## License

MIT
