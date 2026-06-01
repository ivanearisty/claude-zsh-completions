#!/usr/bin/env python3
"""Parse the Claude Code CLI's --help output and keep _claude in sync with it.

Claude Code is a commander.js program with no built-in completion generator
(tj/commander.js#2008 is still open), so the completion is hand-maintained.
This tool closes the maintenance gap by reading the CLI's own --help screens:

  surface   Print the normalized CLI surface (every flag + command), one per
            line. Useful for humans and as the basis for the other modes.

  check     Diff the live CLI surface against what _claude actually covers and
            exit non-zero on drift, printing exactly which flags/commands were
            added or removed. This is the version-tracking gate run in CI.

  generate  Emit a complete _arguments-based _claude to stdout, regenerated
            from --help. The hand-written dynamic block (the --resume session
            lister, delimited by the DYN_BEGIN/DYN_END markers) is preserved
            verbatim, and a small OVERRIDES table supplies the file/dynamic
            completion actions that --help text alone can't imply.

By default each mode shells out to `claude ... --help`. Pass --help-dir DIR to
parse pre-captured screens instead (used by the test suite): DIR must contain
_root.txt and <subcommand>.txt files.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field

# --- completion actions that --help text cannot infer -----------------------
# Maps a long flag (without --) to the zsh action string used after its value
# placeholder. Anything not listed gets a bare " " (accept any word) for
# value flags, the parsed (choices ...) when --help lists them, or nothing for
# booleans. --resume points at the dynamic session lister.
OVERRIDES: dict[str, str] = {
    "resume": "_claude_sessions",
    "add-dir": "_files -/",
    "settings": "_files",
    "mcp-config": "_files",
    "debug-file": "_files",
    "system-prompt-file": "_files",
    "append-system-prompt-file": "_files",
    "plugin-dir": "_files -/",
    # choices --help doesn't enumerate but we want to suggest:
    "model": "(opus sonnet haiku claude-opus-4-8 claude-opus-4-7 "
             "claude-sonnet-4-6 claude-haiku-4-5 claude-haiku-4-5-20251001)",
}

DYN_BEGIN = "# >>> dynamic-sessions (preserved by tools/cli_surface.py) >>>"
DYN_END = "# <<< dynamic-sessions <<<"


# --- data model -------------------------------------------------------------
@dataclass
class Opt:
    aliases: list[str]            # e.g. ["-r", "--resume"]
    takes_value: bool = False
    optional_value: bool = False  # [value] vs <value>
    variadic: bool = False        # value placeholder had "..."
    choices: list[str] = field(default_factory=list)
    desc: str = ""

    @property
    def longs(self) -> list[str]:
        return [a for a in self.aliases if a.startswith("--")]

    @property
    def primary(self) -> str:
        longs = self.longs
        return longs[0] if longs else self.aliases[0]


@dataclass
class Cmd:
    names: list[str]              # ["plugin", "plugins"]
    desc: str = ""

    @property
    def primary(self) -> str:
        return self.names[0]


# --- help acquisition -------------------------------------------------------
def get_help(path: list[str], help_dir: str | None) -> str:
    if help_dir:
        fname = "_root" if not path else "_".join(path)
        fpath = os.path.join(help_dir, f"{fname}.txt")
        if not os.path.exists(fpath):
            return ""
        with open(fpath, encoding="utf-8") as fh:
            return fh.read()
    try:
        out = subprocess.run(
            ["claude", *path, "--help"],
            capture_output=True, text=True, timeout=60,
        )
        return out.stdout
    except Exception as exc:  # pragma: no cover - defensive
        print(f"warning: `claude {' '.join(path)} --help` failed: {exc}", file=sys.stderr)
        return ""


# --- parsing ----------------------------------------------------------------
SECTION_RE = re.compile(r"^[A-Z][A-Za-z ]+:$")
OPT_START_RE = re.compile(r"^  (-\S)")        # 2 spaces then a dash-flag
CMD_START_RE = re.compile(r"^  ([^\s-]\S*)")  # 2 spaces then a non-dash token
PLACEHOLDER_RE = re.compile(r"[<\[]([^>\]]*)[>\]]")
CHOICES_RE = re.compile(r'choices:\s*((?:"[^"]*"\s*,?\s*)+)')


def _block(help_text: str, header: str) -> list[str]:
    """Return the lines belonging to the `header:` section."""
    lines = help_text.splitlines()
    out: list[str] = []
    in_block = False
    for ln in lines:
        if ln.strip() == f"{header}:":
            in_block = True
            continue
        if in_block:
            if SECTION_RE.match(ln) and ln.strip() != f"{header}:":
                break
            out.append(ln)
    return out


def _entries(block: list[str], start_re: re.Pattern) -> list[list[str]]:
    """Group a section's lines into per-entry chunks (an entry + its wrapped
    continuation lines)."""
    chunks: list[list[str]] = []
    cur: list[str] = []
    for ln in block:
        if start_re.match(ln):
            if cur:
                chunks.append(cur)
            cur = [ln]
        elif cur and ln.strip():
            cur.append(ln)
    if cur:
        chunks.append(cur)
    return chunks


def parse_options(help_text: str) -> list[Opt]:
    opts: list[Opt] = []
    for chunk in _entries(_block(help_text, "Options"), OPT_START_RE):
        first = chunk[0][2:]  # drop leading 2 spaces
        # spec is the part before a run of 2+ spaces; if none, the whole line
        m = re.search(r"\s{2,}", first)
        if m:
            spec, desc_first = first[: m.start()], first[m.end():]
            rest = chunk[1:]
        else:
            spec, desc_first = first, ""
            rest = chunk[1:]
        desc = " ".join([desc_first, *(l.strip() for l in rest)]).strip()

        aliases = [a.strip() for a in spec.split(",")]
        # the value placeholder rides on the spec; strip it off each alias
        ph = PLACEHOLDER_RE.search(spec)
        clean_aliases, opt_flags = [], None
        for a in aliases:
            pm = PLACEHOLDER_RE.search(a)
            if pm:
                opt_flags = a[: pm.start()].strip()
                clean_aliases.append(opt_flags)
            else:
                clean_aliases.append(a)
        clean_aliases = [a for a in clean_aliases if a]

        opt = Opt(aliases=clean_aliases, desc=desc)
        if ph:
            raw = spec[ph.start(): ph.end()]
            opt.takes_value = True
            opt.optional_value = raw.startswith("[")
            opt.variadic = "..." in raw
        cm = CHOICES_RE.search(desc)
        if cm:
            opt.choices = re.findall(r'"([^"]*)"', cm.group(1))
        opts.append(opt)
    return opts


def parse_commands(help_text: str) -> list[Cmd]:
    cmds: list[Cmd] = []
    for chunk in _entries(_block(help_text, "Commands"), CMD_START_RE):
        first = chunk[0][2:]
        token = first.split()[0]                  # "plugin|plugins"
        names = token.split("|")
        m = re.search(r"\s{2,}", first)
        desc = first[m.end():].strip() if m else ""
        desc = " ".join([desc, *(l.strip() for l in chunk[1:])]).strip()
        if names and names[0] != "help":
            cmds.append(Cmd(names=names, desc=desc))
    return cmds


# --- surface ----------------------------------------------------------------
def cli_surface(help_dir: str | None) -> tuple[set[str], set[str]]:
    """Return (set of long flags, set of command names) across root + subcmds."""
    root = get_help([], help_dir)
    flags = {a for o in parse_options(root) for a in o.longs}
    cmds = parse_commands(root)
    names: set[str] = set()
    for c in cmds:
        names.update(c.names)
    return flags, names


# --- check ------------------------------------------------------------------
def covered_tokens(claude_file: str) -> tuple[set[str], set[str]]:
    """Long flags and command names that literally appear in _claude."""
    with open(claude_file, encoding="utf-8") as fh:
        text = fh.read()
    flags = set(re.findall(r"--[a-zA-Z][a-zA-Z0-9-]+", text))
    # command names live in the `commands=( 'name:desc' ... )` arrays
    cmds = set(re.findall(r"^\s*'([a-z][a-z0-9-]*):", text, re.MULTILINE))
    return flags, cmds


def do_check(claude_file: str, help_dir: str | None) -> int:
    cli_flags, cli_cmds = cli_surface(help_dir)
    cov_flags, cov_cmds = covered_tokens(claude_file)

    missing_flags = sorted(cli_flags - cov_flags)
    missing_cmds = sorted(cli_cmds - cov_cmds)
    # "extra" = present in completion but no longer in CLI (likely removed)
    KNOWN_NON_CLI = {"--no-chrome", "--no-session-persistence", "--allowed-tools",
                     "--disallowed-tools"}  # negations/aliases help may not list
    extra_flags = sorted(cov_flags - cli_flags - KNOWN_NON_CLI)

    drift = bool(missing_flags or missing_cmds)
    if missing_flags:
        print("MISSING flags (in `claude --help`, absent from _claude):")
        for f in missing_flags:
            print(f"  + {f}")
    if missing_cmds:
        print("MISSING commands (in `claude --help`, absent from _claude):")
        for c in missing_cmds:
            print(f"  + {c}")
    if extra_flags:
        print("note: flags in _claude not seen in root --help "
              "(aliases/negations/subcommand-only — review, not necessarily wrong):")
        for f in extra_flags:
            print(f"  ? {f}")
    if not drift:
        print(f"OK: _claude covers all {len(cli_flags)} flags and "
              f"{len(cli_cmds)} commands from `claude --help`.")
    return 1 if drift else 0


# --- generate ---------------------------------------------------------------
def _zq(s: str) -> str:
    """Quote a description for use inside a zsh single-quoted _arguments spec."""
    return s.replace("'", "'\\''").replace("[", "\\[").replace("]", "\\]")


def _action_for(opt: Opt) -> str:
    """The `:msg:action` (or `::msg:action`) tail for one option spec."""
    if not opt.takes_value:
        return ""
    name = opt.primary.lstrip("-")
    msg = name
    ovr = OVERRIDES.get(name)
    if opt.choices:
        action = "(" + " ".join(opt.choices) + ")"
    elif ovr:
        action = ovr
    else:
        action = " "
    sep = "::" if opt.optional_value else ":"
    # optional values with no real suggestion use the empty action ( ) so they
    # never swallow the following flag.
    if opt.optional_value and not opt.choices and not ovr:
        action = "( )"
    return f"{sep}{msg}:{action}"


def _opt_spec(opt: Opt) -> str:
    repeat = "\\*" if opt.variadic else ""
    tail = _action_for(opt)
    if len(opt.aliases) > 1:
        # zsh exclusion list must be single-quoted so brace expansion yields one
        # word per alias: '(-a -b)'{-a,-b}'[desc]tail'
        excl = "'(" + " ".join(opt.aliases) + ")'"
        body = "{" + ",".join(opt.aliases) + "}"
        return f"{repeat}{excl}{body}'[{_zq(opt.desc)}]{tail}'"
    return f"{repeat}'{opt.aliases[0]}[{_zq(opt.desc)}]{tail}'"


def read_dynamic_block(claude_file: str) -> str:
    with open(claude_file, encoding="utf-8") as fh:
        text = fh.read()
    if DYN_BEGIN in text and DYN_END in text:
        return text[text.index(DYN_BEGIN): text.index(DYN_END) + len(DYN_END)]
    return ""  # markers not present yet


def do_generate(claude_file: str, help_dir: str | None) -> int:
    root = get_help([], help_dir)
    opts = parse_options(root)
    cmds = parse_commands(root)
    dyn = read_dynamic_block(claude_file)

    out: list[str] = []
    out.append("#compdef claude")
    out.append("# Zsh completions for the Claude Code CLI.")
    out.append("# Top-level options/commands GENERATED from `claude --help` by")
    out.append("# tools/cli_surface.py; the dynamic session block is preserved.")
    out.append("# https://github.com/ivanearisty/claude-zsh-completions")
    out.append("")
    if dyn:
        out.append(dyn)
        out.append("")
    out.append("_claude() {")
    out.append("  local context state state_descr line")
    out.append("  typeset -A opt_args")
    out.append("")
    out.append("  _arguments -C \\")
    for o in opts:
        out.append("    " + _opt_spec(o) + " \\")
    out.append("    '1:: :->command' \\")
    out.append("    '*::arg:->args'")
    out.append("")
    out.append("  case $state in")
    out.append("    command)")
    out.append("      local -a commands")
    out.append("      commands=(")
    for c in cmds:
        for n in c.names:
            out.append(f"        '{n}:{_zq(c.desc)}'")
    out.append("      )")
    out.append("      _describe 'command' commands")
    out.append("      ;;")
    out.append("  esac")
    out.append("}")
    out.append("")
    out.append('_claude "$@"')
    sys.stdout.write("\n".join(out) + "\n")
    return 0


# --- cli --------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["surface", "check", "generate"])
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--claude-file", default=os.path.join(repo_root, "_claude"),
                    help="path to the _claude completion file (default: repo _claude)")
    ap.add_argument("--help-dir", default=None,
                    help="parse pre-captured *.txt help screens from DIR instead "
                         "of invoking `claude`")
    args = ap.parse_args()

    if args.mode == "surface":
        flags, cmds = cli_surface(args.help_dir)
        for f in sorted(flags):
            print(f"flag {f}")
        for c in sorted(cmds):
            print(f"cmd  {c}")
        return 0
    if args.mode == "check":
        return do_check(args.claude_file, args.help_dir)
    if args.mode == "generate":
        return do_generate(args.claude_file, args.help_dir)
    return 2


if __name__ == "__main__":
    sys.exit(main())
