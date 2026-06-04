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

## Testing

`fish tests/check.fish` — for every `completions/*.fish`: asserts it parses
(`fish -n`) and that `complete -C "<tool> "` yields a non-empty, non-filename
candidate set. Run before any commit in build phase.

## Git / PR

- Dev phase: commit frequently, local only.
- Build phase: squash WIP into per-tool logical commits; open small,
  reviewable PRs upstream (fish maintainers prefer per-tool / small thematic
  batches over one mega-PR). Push only with PROMPTER approval.
