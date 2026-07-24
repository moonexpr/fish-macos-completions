# AGENTS.md — fish-macos-completions

This file provides guidance to AGENTS working on fish completions for macOS system utilities in this repository. Operational rules and architecture principles live in `~/.claude/CLAUDE.md` (the global config). This file adds project-specific conventions and k-shot examples so agents do not repeat mistakes already corrected by upstream review.

> Destination: completions are authored to drop unchanged into fish-shell `share/completions/`, tracked by upstream issue fish-shell#3525.

---

## Role

The AGENT is a completion author. It reads man pages, writes idiomatic fish script, runs the local parse + smoke harness, and produces commits that are ready for upstream review. The PROMPTER is the human gate for pushing branches and opening upstream PRs.

---

## Mission

Add or improve fish completions for macOS system utilities. A completion file is correct when:

1. It parses with `fish -n`.
2. It is normalized with `fish_indent`.
3. `complete -C "<tool> "` yields a non-empty, non-filename candidate set (per `tests/check.fish`).
4. Every flag/verb has a man-page-grounded `-d` description.
5. Live enumeration uses only fast, unprivileged commands and degrades to empty.
6. It follows the anti-patterns below — no redundant guards, no global state, no `ls` parsing, no `0/1` booleans.

---

## Principles

1. **Exit status is the contract.** A helper that finds a token returns it and exits 0; a helper that finds nothing exits non-zero. Callers use `and`, `or`, `not`, and `$cmd` expansion rather than inventing secondary guards.
2. **One parser per grammar.** If several helpers inspect the same command-line structure, extract a single parser and index it. Do not re-walk tokens in each helper.
3. **Locals over globals.** Completion files are sourced into the user's shell. Use `set -l`. If a helper needs a value from outer scope, use `function --inherit-variable`.
4. **-xpc over -opc.** Use `commandline -xpc` for predicates; it excludes the in-progress token, which is almost always the right behavior.
5. **Anti-patterns are positive examples.** Each rule below shows a bad form and a good form. The bad form is preserved only for recognition, not for use.

---

## Judgment Calls

- **Ambiguous scope:** take the conservative interpretation and note the assumption.
- **New tool vs. fix:** if the PROMPTER asks to add a new completion, finish the current review-fix work first or push it to a separate branch.
- **Live enumeration risk:** if a command might be slow, require root, or hit the network, do not run it on tab. Prefer hard-coded candidate lists or skip the live source.
- **Technical calls are the AGENT's responsibility.** Engineering questions (which predicate form, how to share parsing) are resolved by the AGENT and reported.

---

## Scope Discipline

- One completion file per tool.
- One logical commit per review-fix theme or per new tool.
- Do not mix unrelated refactors with new completions in the same commit.
- If the PROMPTER adds a new request mid-task, apply the defer/expand/pivot rule from `CLAUDE.md`.

---

## Coding Standards

### 1. Rely on exit status instead of redundant guards

Bad:
```fish
function __fish_profiles_using_verb
    set -l v (__fish_profiles_verb 2>/dev/null)
    test -n "$v" && test "$v" = "$argv[1]"
end
```

Good:
```fish
function __fish_profiles_using_verb
    set -l v (__fish_profiles_verb)
    test "$v" = "$argv[1]"
end
```

### 2. Use `true`/`false` for fish booleans, not `0`/`1`

Bad:
```fish
set -l saw_g 0
if test $saw_g -eq 1
    ...
end
```

Good:
```fish
set -l saw_g false
if $saw_g
    ...
end
```

### 3. Parse command-line tokens with `-xpc`

Bad:
```fish
set -l toks (commandline -opc)
```

Good:
```fish
set -l toks (commandline -xpc)
```

### 4. Redirect both streams with `&>/dev/null`

Bad:
```fish
not __fish_hdiutil_verb >/dev/null 2>&1
```

Good:
```fish
not __fish_hdiutil_verb &>/dev/null
```

### 5. Enumerate directories with globs, not `ls`

Bad:
```fish
ls /Volumes | while read -l v
    echo /Volumes/$v
end
```

Good:
```fish
for v in /Volumes/*
    echo $v
end
```

### 6. Never define global variables in completion files

Bad:
```fish
set -g __fish_dscl_ds_found 1
```

Good:
```fish
set -l ds_found
...
if set -q ds_found[1]
    ...
end
```

### 7. Avoid pointless stderr suppression on silent helpers

Bad:
```fish
set -l act (__fish_pmset_action 2>/dev/null)
```

Good:
```fish
set -l act (__fish_pmset_action)
```

### 8. Share positional parsing through one primitive

Bad:
```fish
function __fish_dscl_datasource
    # walks tokens
end
function __fish_dscl_command
    # walks tokens again
end
```

Good:
```fish
function __fish_dscl_at
    set -l pos (__fish_dscl_positionals)
    set -q pos[$argv[1]]; and echo $pos[$argv[1]]
end

function __fish_dscl_datasource
    __fish_dscl_at 1
end

function __fish_dscl_command
    set -l cmd (__fish_dscl_at 2)
    and string trim -l -c - -- $cmd
end
```

### 9. Keep stdout alive for live enumerators

Suppress only stderr when an external list command may error. Suppressing stdout kills the completion candidates.

Bad:
```fish
function __fish_dscl_toplevel
    dscl . -list / &>/dev/null
end
```

Good:
```fish
function __fish_dscl_toplevel
    dscl . -list / 2>/dev/null
end
```

---

## Testing Discipline

Run before every commit:

```bash
fish tests/check.fish
```

Also run:

```bash
for f in completions/*.fish; do fish -n "$f" || echo "SYNTAX ERROR: $f"; done
for f in completions/*.fish; do fish_indent --check "$f" || echo "FORMAT: $f"; done
```

For changes to command-line parsing helpers, add an interactive smoke test:

```fish
fish -i -c '
    source completions/dscl.fish
    commandline -r "dscl . read "
    printf "datasource=%s command=%s\n" (__fish_dscl_datasource) (__fish_dscl_command)
'
```

Use a trailing space in the simulated command line so the current token is empty, matching real tab-completion behavior.

---

## Memory Management

- Learned conventions and upstream feedback go into `PROJECT.md` (this file) or `AGENTS.md`.
- Cross-project tool patterns go into `~/.claude/memory/tools/fish.md`.
- Do not duplicate `~/.claude/CLAUDE.md` content here; point to it instead.

---

## Rules

1. One file per tool, named exactly as the binary: `completions/<tool>.fish`.
2. Helpers are named `__fish_<tool>_<purpose>` and defined in the same file.
3. Use `__fish_use_subcommand` / `__fish_seen_subcommand_from` for true subcommand tools.
4. Use `-o <verb>` plus a `__fish_<tool>_no_verb` predicate for single-dash-long-verb tools.
5. Live enumeration must be fast, unprivileged, and degrade to empty.
6. No invented flags or verbs; ground descriptions in the man page.
7. Commit only after `fish -n` and `fish_indent --check` pass.
8. Push only with PROMPTER approval.
