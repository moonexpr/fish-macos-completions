# PROJECT — fish-macos-completions

fish completions for macOS system utilities that fish does not yet ship.
Destination: upstream fish-shell (`share/completions/`), tracking issue
fish-shell#3525. This repo is the development home; files are authored to drop
in unchanged.

## Layout

```
completions/<tool>.fish   # one file per tool, named exactly as the binary
tests/check.fish          # parse + smoke harness over completions/
WORKPLAN.md               # session task cards + validators
```

## Conventions

- Helpers are functions named `__fish_<tool>_*`, defined in the same file.
- Subcommand tools: `-n __fish_use_subcommand` for verbs, `-n
  '__fish_seen_subcommand_from <verb>'` for a verb's arguments.
- Single-dash-long-verb tools (networksetup, systemsetup): verbs as `-o <verb>`,
  gated by a `__fish_<tool>_no_verb` predicate; arguments keyed off the verb on
  the command line.
- Every subcommand/verb carries a `-d` description grounded in the tool's man
  page. No invented flags.
- Live enumeration only via fast, unprivileged list commands, always
  `2>/dev/null`, degrading to empty. Never run network/slow/sudo commands on tab
  (`softwareupdate -l`, full `system_profiler`, etc. are excluded).
- `-f`/`-x` on subcommands that take no path; keep file completion for real path
  operands.

## Anti-patterns learned from upstream review

These patterns came from fish-shell maintainer feedback on PR #12874. Prefer the
**good** form; the **bad** form is shown only so we recognize it.

### 1. Rely on exit status instead of redundant guards

A helper that finds a token already signals "not found" by returning non-zero.
Do not add an extra empty-string test.

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

`-xpc` gives tokens up to the cursor, excluding the in-progress token, which is
almost always what completion predicates want.

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

Completion files are sourced into the user's shell. Keep state local. Capture a
local in a function with `--inherit-variable` if a helper needs it.

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

If a helper already writes nothing to stderr and returns non-zero on "not
found", do not wrap it in `2>/dev/null`.

Bad:
```fish
set -l act (__fish_pmset_action 2>/dev/null)
```

Good:
```fish
set -l act (__fish_pmset_action)
```

### 8. Share positional parsing through one primitive

When several helpers inspect the same command-line structure, extract one
parser and index it rather than re-walking tokens in each helper.

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

## Testing

`fish tests/check.fish` — for every `completions/*.fish`: asserts it parses
(`fish -n`) and that `complete -C "<tool> "` yields a non-empty, non-filename
candidate set. Run before any commit in build phase.

## Git / PR

- Dev phase: commit frequently, local only.
- Build phase: squash WIP into per-tool logical commits; open small,
  reviewable PRs upstream (fish maintainers prefer per-tool / small thematic
  batches over one mega-PR). Push only with PROMPTER approval.
