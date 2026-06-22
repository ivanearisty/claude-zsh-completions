#!/usr/bin/env zsh
# Test suite for claude-zsh-completions.
#
# Runs three layers, all hermetic (a throwaway CLAUDE_CONFIG_DIR with fixture
# sessions — never the caller's real ~/.claude):
#   1. lint     — `zsh -n` parse + clean `compinit` load
#   2. unit     — helper functions (dir encoding, reltime, session listing)
#   3. e2e      — a real TAB driven through zsh/zpty inserts a session UUID
#
# Usage: zsh test/run.zsh        (exit 0 = all passed, non-zero = failures)
emulate -L zsh
setopt no_unset

typeset -g ROOT="${0:A:h:h}"          # repo root (test/run.zsh -> repo)
typeset -g COMPFILE="$ROOT/_claude"
# Results go to a temp file so counts survive the ( ) subshells used to scope
# per-section cd / compadd overrides.
typeset -g RESULTS; RESULTS="$(mktemp)"

ok()   { print -P "  %F{green}ok%f   $1"; print P >> "$RESULTS" }
nope() { print -P "  %F{red}FAIL%f $1"; print "F  $1" >> "$RESULTS" }
is()   { [[ "$1" == "$2" ]] && ok "$3" || { nope "$3"; print "       want: [$2]"; print "       got:  [$1]" } }
section() { print -P "%F{cyan}== $1 ==%f" }

# Load just the helper region (everything before _claude_auth) so we can call
# the helpers directly without the compsys machinery the full file needs.
load_helpers() { source <(sed -n '1,/^_claude_auth() {/p' "$COMPFILE" | sed '$d') }

# Build a hermetic config dir with N fixture sessions for a given working dir.
# Echoes the config dir path; sets global FIX_IDS / FIX_TITLES parallel arrays.
typeset -ga FIX_IDS FIX_TITLES
make_fixtures() {
  local workdir=$1 cfg; cfg="$(mktemp -d)"
  local enc="${workdir//[^a-zA-Z0-9]/-}"
  local pdir="$cfg/projects/$enc"
  mkdir -p "$pdir"
  FIX_IDS=(); FIX_TITLES=()
  local -a specs=(
    "11111111-1111-1111-1111-111111111111|First fixture session"
    "22222222-2222-2222-2222-222222222222|Second fixture session"
    "33333333-3333-3333-3333-333333333333|"   # no ai-title -> falls back to user prompt
  )
  local s id title
  for s in $specs; do
    id="${s%%|*}"; title="${s#*|}"
    {
      print -r -- '{"type":"permission-mode","permissionMode":"default","sessionId":"'"$id"'"}'
      if [[ -n $title ]]; then
        print -r -- '{"type":"ai-title","aiTitle":"'"$title"'","sessionId":"'"$id"'"}'
      fi
      print -r -- '{"type":"user","message":{"role":"user","content":"prompt for '"$id"'"}}'
    } > "$pdir/$id.jsonl"
    FIX_IDS+=( "$id" ); FIX_TITLES+=( "${title:-prompt for $id}" )
    sleep 0.01   # distinct mtimes so newest-first ordering is deterministic
  done
  print -r -- "$cfg"
}

# ---------------------------------------------------------------------------
section "lint"
if zsh -n "$COMPFILE"; then ok "_claude parses (zsh -n)"; else nope "_claude has a syntax error"; fi

# clean compinit load in an isolated zsh
if zsh -f -c '
    fpath=( '"$ROOT"' $fpath )
    autoload -Uz compinit && compinit -u 2>/tmp/.cc_compinit_err
    [[ -s /tmp/.cc_compinit_err ]] && { cat /tmp/.cc_compinit_err >&2; exit 1 }
    exit 0' 2>/dev/null
then ok "compinit loads cleanly"; else nope "compinit emitted warnings/errors"; fi
rm -f /tmp/.cc_compinit_err

# ---------------------------------------------------------------------------
section "unit: helpers"
(
  load_helpers
  # dir encoding
  is "$(PWD=/Users/x/Ivan\'s\ Vault _claude_project_session_dir)" \
     "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects/-Users-x-Ivan-s-Vault" \
     "_claude_project_session_dir encodes non-alphanumerics to -"

  # reltime buckets
  zmodload zsh/datetime
  is "$(_claude_session_reltime $(( EPOCHSECONDS - 10 )))"    "just now" "reltime: <60s -> just now"
  is "$(_claude_session_reltime $(( EPOCHSECONDS - 300 )))"   "5m ago"   "reltime: minutes"
  is "$(_claude_session_reltime $(( EPOCHSECONDS - 7200 )))"  "2h ago"   "reltime: hours"
  is "$(_claude_session_reltime $(( EPOCHSECONDS - 172800 )))" "2d ago"  "reltime: days"
)

# ---------------------------------------------------------------------------
section "unit: _claude_sessions over fixtures"
(
  load_helpers
  local workdir; workdir="$(mktemp -d)"
  local cfg; cfg="$(make_fixtures "$workdir")"
  export CLAUDE_CONFIG_DIR="$cfg"
  cd "$workdir"

  # capture compadd args without shadowing the caller's ids/disp locals
  compadd() {
    local -a _ci _cd
    while (( $# )); do
      case $1 in
        -d) _cd=( ${(P)2} ); shift 2;;
        -a) _ci=( ${(P)2} ); shift 2;;
        -V) shift 2;; -Q) shift;; *) shift;;
      esac
    done
    print -rl -- $_ci > "$cfg/.got_ids"
    print -rl -- $_cd > "$cfg/.got_disp"
  }
  _claude_sessions
  local -a got_ids got_disp
  got_ids=( ${(f)"$(<"$cfg/.got_ids")"} )
  got_disp=( ${(f)"$(<"$cfg/.got_disp")"} )

  is "${#got_ids}" "3" "offers all 3 fixture sessions"
  # newest first: fixture #3 was written last
  is "${got_ids[1]}" "33333333-3333-3333-3333-333333333333" "newest session listed first"
  [[ "${got_disp[1]}" == *"prompt for 33333333"* ]] && ok "untitled session falls back to first user prompt" || nope "fallback title wrong: ${got_disp[1]}"
  [[ "${got_disp[3]}" == "First fixture session"* ]] && ok "ai-title used as label" || nope "ai-title label wrong: ${got_disp[3]}"

  # jq-less path: same fixtures, jq masked out
  () {
    jq() { return 127 }   # simulate jq absent for title scrape fallback
    _claude_session_cache=()
    _claude_sessions
    local -a ids2; ids2=( ${(f)"$(<"$cfg/.got_ids")"} )
    is "${#ids2}" "3" "jq-less fallback still lists sessions"
  }
  rm -rf "$cfg" "$workdir"
)

# ---------------------------------------------------------------------------
section "e2e: real TAB via zpty"
if zmodload zsh/zpty 2>/dev/null; then
  load_helpers
  local workdir; workdir="$(mktemp -d)"
  # single fixture so the completion is UNIQUE and gets inserted into the buffer
  local cfg enc pdir uuid="abcdef01-2345-6789-abcd-ef0123456789"
  cfg="$(mktemp -d)"; enc="${workdir//[^a-zA-Z0-9]/-}"; pdir="$cfg/projects/$enc"
  mkdir -p "$pdir"
  print -r -- '{"type":"ai-title","aiTitle":"only session","sessionId":"'"$uuid"'"}' > "$pdir/$uuid.jsonl"

  local OUT=""
  # The pty drains echo back the keystrokes/prompt; keep that noise off stdout.
  # OUT is a variable so it survives the fd redirect on this group.
  {
    zmodload zsh/zselect 2>/dev/null
    zpty CC "exec zsh -f"
    zpty -w CC "export CLAUDE_CONFIG_DIR=$cfg"
    zpty -w CC "fpath=( $ROOT \$fpath ); autoload -Uz compinit; compinit -u"
    zpty -w CC "claude(){ : }"
    zpty -w CC 'bindkey "^I" expand-or-complete'
    zpty -w CC "cd $workdir"
    local j; repeat 30 { zpty -r -t CC j 2>/dev/null && : }
    zpty -w CC $'claude --resume \t'
    integer i
    for (( i=0; i<60; i++ )); do
      repeat 5 { zpty -r -t CC j 2>/dev/null && OUT+=$j }
      [[ $OUT == *$uuid* ]] && break
      zselect -t 10 2>/dev/null || sleep 0.1
    done
    zpty -d CC 2>/dev/null || true
  } >/dev/null 2>&1
  [[ $OUT == *$uuid* ]] && ok "TAB on 'claude --resume ' inserts the unique session UUID" \
                        || nope "e2e: UUID not inserted by TAB"
  rm -rf "$cfg" "$workdir"
else
  print -P "  %F{yellow}skip%f zsh/zpty unavailable"
fi

# ---------------------------------------------------------------------------
section "tool: cli_surface.py"
if (( $+commands[python3] )); then
  local fixtures="$ROOT/test/fixtures/help"
  # positive: committed _claude covers the fixture CLI surface
  if python3 "$ROOT/tools/cli_surface.py" check --help-dir "$fixtures" \
       --claude-file "$COMPFILE" >/dev/null 2>&1
  then ok "check: _claude has zero drift against the help fixture"
  else nope "check: unexpected drift against the committed help fixture"; fi

  # negative: a fixture with an extra flag must be reported as drift. Inject it
  # INSIDE the Options: block (the parser ignores anything after Commands:).
  local dfix; dfix="$(mktemp -d)"
  awk '1; /^Options:/{print "  --xyzzy-not-real <x>                  A flag that does not exist"}' \
     "$fixtures/_root.txt" > "$dfix/_root.txt"
  if python3 "$ROOT/tools/cli_surface.py" check --help-dir "$dfix" \
       --claude-file "$COMPFILE" >/dev/null 2>&1
  then nope "check: failed to detect an injected missing flag"
  else ok "check: detects injected missing flag (exit 1)"; fi
  rm -rf "$dfix"

  # generate: output must parse as zsh
  local gen; gen="$(mktemp)"
  python3 "$ROOT/tools/cli_surface.py" generate --help-dir "$fixtures" \
     --claude-file "$COMPFILE" > "$gen" 2>/dev/null
  if zsh -n "$gen" 2>/dev/null; then ok "generate: emitted _claude parses (zsh -n)"
  else nope "generate: emitted _claude has a syntax error"; fi
  grep -q '_claude_sessions()' "$gen" && ok "generate: preserves the dynamic block" \
                                      || nope "generate: lost the dynamic block"
  rm -f "$gen"
else
  print -P "  %F{yellow}skip%f python3 unavailable"
fi

# ---------------------------------------------------------------------------
integer PASS FAIL
PASS=$(grep -c '^P' "$RESULTS")   # grep -c prints 0 (and exits 1) on no match
FAIL=$(grep -c '^F' "$RESULTS")
print
if (( FAIL )); then
  print -P "%F{red}failed assertions:%f"
  grep '^F' "$RESULTS" | sed 's/^F  /  - /'
fi
print -P "%F{cyan}== summary ==%f  $PASS passed, $FAIL failed"
rm -f "$RESULTS"
(( FAIL == 0 ))
