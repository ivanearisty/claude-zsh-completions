# claude-zsh-completions

Zsh tab-completions for the [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI.

Covers all flags, subcommands (`auth`, `mcp`, `install`, `doctor`, `plugin`), and their nested options.

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
auth     -- Manage authentication
doctor   -- Check the health of your Claude Code auto-updater
install  -- Install Claude Code native build
mcp      -- Configure and manage MCP servers
plugin   -- Manage Claude Code plugins

$ claude --<TAB>
--add-dir          --debug-file       --model          --print
--agent            --effort           --mcp-config     --resume
...
```

## License

MIT
