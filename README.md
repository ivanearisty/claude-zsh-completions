# claude-zsh-completions

Zsh tab-completions for the [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI (tracks `v2.1.x`).

Covers every flag, subcommand (`agents`, `auth`, `auto-mode`, `doctor`, `install`, `mcp`, `plugin`, `project`, `setup-token`, `ultrareview`, `update`), and their nested options — including deep completions for `mcp add`, `plugin install/uninstall/marketplace/tag/prune`, `auth login/status`, `auto-mode critique`, `project purge`, and more.

Handles a few edge cases that trip up naive completions:

- **`--resume`/`-r` completes your actual conversations.** `claude --resume <TAB>` lists the current project's resumable sessions, newest first, each labelled with its AI-generated title and a relative timestamp — pick one and the real session UUID is inserted. (See [Dynamic session completion](#dynamic-session-completion).)
- Flags with optional values (e.g. `--resume [id]`, `--from-pr [value]`, `--worktree [name]`, `--remote-control [name]`, `--debug [filter]`) no longer swallow the next flag. `claude --resume <id> --<TAB>` continues to complete flags like `--model`, `--effort`, etc.
- Repeatable flags (`--add-dir`, `--file`, `--mcp-config`, `--plugin-dir`, `--plugin-url`, `mcp add -e/-H`) can be passed multiple times.
- The positional command slot is optional, so trailing flags after a free-form prompt still complete.

## Dynamic session completion

`claude --resume` (and `-r`) resumes a conversation in the *current directory*. Claude Code stores each conversation as a JSONL transcript under `~/.claude/projects/<encoded-cwd>/<uuid>.jsonl`, so the completion reads that directory and offers the real sessions:

```
$ claude --resume <TAB>
Enhance Claude CLI zsh completions with resume flag  ·  just now  ·  46c54acf
Enable completions for homebrew packages             ·  2m ago    ·  0647ebba
Transcribe Zoom recordings with Whisper              ·  7h ago    ·  e2f2fa17
Set up SSH tunnel to Piazza dev app                  ·  8h ago    ·  6e9aee95
...
```

The label is the session's AI-generated title (the `ai-title` event in the transcript), falling back to the first user prompt, then `(untitled)`. Selecting an entry inserts the full session UUID, so Claude resumes that conversation directly instead of opening the picker. (Typing a free-form search term still works too — Claude's picker matches it.)

Notes:

- **Scoped to `$PWD`.** Only sessions started in the current directory are shown, matching how `--resume` itself behaves.
- **Cached for speed.** Titles are extracted once and memoised per `(directory, newest-mtime, session-count)` in a shell-global array, so repeated `<TAB>` is instant. The cache self-invalidates whenever a session is added, removed, or touched.
- **`jq` is optional.** When installed it parses titles robustly; otherwise a lightweight fallback is used.

Tunables (environment variables):

| Variable | Default | Effect |
| --- | --- | --- |
| `CLAUDE_CONFIG_DIR` | `~/.claude` | Where Claude Code stores its `projects/` transcripts. |
| `CLAUDE_RESUME_MAX` | `50` | Cap on how many recent sessions are scanned/offered. |

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
agents       -- Manage background and configured agents
auth         -- Manage authentication
auto-mode    -- Inspect auto mode classifier configuration
doctor       -- Check the health of your Claude Code auto-updater
install      -- Install Claude Code native build
mcp          -- Configure and manage MCP servers
plugin       -- Manage Claude Code plugins
project      -- Manage Claude Code project state
setup-token  -- Set up a long-lived authentication token
ultrareview  -- Run a cloud-hosted multi-agent code review
update       -- Check for updates and install if available

$ claude --<TAB>
--add-dir                                  --model
--agent                                    --name
--agents                                   --no-chrome
--allow-dangerously-skip-permissions       --no-session-persistence
--append-system-prompt                     --output-format
--append-system-prompt-file                --permission-mode
--bare                                     --plugin-dir
--brief                                    --plugin-url
--chrome                                   --print
--continue                                 --remote-control
--debug                                    --remote-control-session-name-prefix
--debug-file                               --replay-user-messages
--disable-slash-commands                   --resume
--effort                                   --session-id
--exclude-dynamic-system-prompt-sections   --setting-sources
--fallback-model                           --settings
--file                                     --strict-mcp-config
--fork-session                             --system-prompt
--from-pr                                  --system-prompt-file
--ide                                      --tmux
--include-hook-events                      --tools
--include-partial-messages                 --verbose
--input-format                             --worktree
--json-schema                              ...
--max-budget-usd
--mcp-config

$ claude --resume <id> --<TAB>      # still completes flags
--model    --effort   --tools   ...

$ claude mcp <TAB>
add                       -- Add an MCP server to Claude Code
add-from-claude-desktop   -- Import MCP servers from Claude Desktop
add-json                  -- Add an MCP server (stdio or SSE) with a JSON string
get                       -- Get details about an MCP server
list                      -- List configured MCP servers
remove                    -- Remove an MCP server
reset-project-choices     -- Reset approved/rejected project-scoped servers
serve                     -- Start the Claude Code MCP server

$ claude plugin <TAB>
install      -- Install a plugin from available marketplaces
uninstall    -- Uninstall an installed plugin
list         -- List installed plugins
enable       -- Enable a disabled plugin
disable      -- Disable an enabled plugin
update       -- Update a plugin to the latest version
validate     -- Validate a plugin or marketplace manifest
marketplace  -- Manage Claude Code marketplaces
tag          -- Create a {name}--v{version} git tag for a plugin release
prune        -- Remove auto-installed dependencies that are no longer needed
```

## License

MIT
