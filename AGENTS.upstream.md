# AGENTS.md — fish-shell

This file provides guidance to AGENTS (automated contributors / LLMs) working
in the fish-shell repository.

The authoritative source for contribution rules is
`CONTRIBUTING.rst <CONTRIBUTING.rst>`__; for project orientation, see
`README.rst <README.rst>`__. This file condenses those rules to the checks an
agent must run, and adds k-shot examples of mistakes commonly made by
generated code, so they can be avoided.

---

## Role

The AGENT is a contributor. It writes idiomatic Rust or fish script, runs the
formatters and tests below, and prepares commits that follow fish-shell's
linear, recipe-style history. A human contributor reviews the result and
opens the upstream PR; the AGENT never pushes or opens PRs itself.

---

## Repository map

| Area | Where | Language |
|------|-------|----------|
| Shell implementation | `src/` (unit tests inline in `mod tests {}`) | Rust |
| Completions | `share/completions/` | fish script |
| Runtime functions | `share/functions/` | fish script |
| User documentation | `doc_src/` (Sphinx) | reST |
| System tests | `tests/checks/` (littlecheck), `tests/pexpects/` (pexpect) | fish / Python |
| Translations | `localization/` | PO / FTL |

User-visible changes need a `CHANGELOG.rst` entry.

---

## Build, format, test

```sh
cargo build                                  # debug build
cargo xtask format --all                     # rustfmt + fish_indent + ruff format
cargo test                                   # Rust unit tests
tests/test_driver.py target/debug            # system tests (or one: ... tests/checks/abbr.fish)
cargo xtask check                            # everything: all tests + linters
```

Rules that apply to every change:

1. **Every commit passes the checks.** Formatted (`cargo xtask format`),
   parses/compiles, tests green — per commit, not just at branch tip.
2. **No fixup commits.** On review feedback, rewrite the relevant commits
   directly (amend / interactive rebase). Rebase on master rather than
   merging. Never rewrite history that is already on master.
3. **`Fixes #<n>`** at the end of the commit description when a commit closes
   an issue.
4. **Add tests with behavior changes.** Prefer littlecheck tests in
   `tests/checks` (fish scripts with expected output in `# CHECK:` /
   `# CHECKERR:` comments); use pexpect only when real interactivity is
   required.
5. **If behavior cannot be verified** — a flag's semantics, a platform
   difference, an untestable path — say so in the PR notes rather than
   guessing.

---

## Contributing completions

The rest of this file covers `share/completions/<command>.fish`, the most
common target for generated contributions.

A completion script is ready for review when:

1. It parses with `fish -n` and is formatted with `fish_indent`.
2. It follows the conventions in `CONTRIBUTING.rst`.
3. It avoids the bad patterns listed below.
4. Descriptions are grounded in the command's man page, start with a capital
   letter, have no trailing period, and are short (aim ≤ 40 characters).

A minimal idiomatic completion, for shape:

```fish
complete -c mycmd -f
complete -c mycmd -s v -l verbose -d "Print more output"
complete -c mycmd -n __fish_use_subcommand -a start -d "Start the service"
complete -c mycmd -n "__fish_seen_subcommand_from start" -a "(mycmd --list 2>/dev/null)"
```

### Principles

1. **Rely on exit status.** A helper that finds a token returns it and exits 0;
   otherwise it exits non-zero. Do not add redundant empty-string guards.
2. **Use fish idioms.** Prefer `true`/`false` over `0`/`1`; use globs instead of
   parsing `ls`; redirect both streams with `&>/dev/null`.
3. **-xpc over -opc.** Use `commandline -xpc` for predicates; it excludes the
   in-progress token, which is almost always the desired behavior.
4. **Locals only.** Completion files are sourced into the user's shell. Never
   define global variables; use `set -l` and `function --inherit-variable`.
5. **One parser per grammar.** If multiple helpers inspect the same command-line
   structure, extract a single parser and index it rather than re-walking tokens.
6. **Suppress a stream only when it needs suppressing.** Silence stderr on
   commands that actually emit noise; never silence stdout you intend to
   capture, and never blanket-silence helpers that are already silent.
7. **Fast, unprivileged enumeration only.** Completions run synchronously on
   every Tab press inside the user's interactive shell; anything slow,
   privileged, or networked degrades it.

### Common mistakes (bad → good)

| Mistake | Bad | Good |
|---------|-----|------|
| Redundant empty-string guard (helper already signals via exit status) | `test -n "$v" && test "$v" = "$argv[1]"` | `test "$v" = "$argv[1]"` |
| Token list includes the in-progress token | `commandline -opc` | `commandline -xpc` |
| Verbose redirect | `>/dev/null 2>&1` | `&>/dev/null` |
| Parsing `ls` | `ls /Volumes \| while read -l v` | `for v in /Volumes/*` |
| Suppressing stderr of a silent helper | `(__fish_pmset_action 2>/dev/null)` | `(__fish_pmset_action)` |
| Suppressing stdout of a live enumerator (discards its results) | `dscl . -list / &>/dev/null` | `dscl . -list / 2>/dev/null` |

Three mistakes involve state and need full context.

**0/1 boolean flags** — use `true`/`false`, which are commands, so the
variable itself is the condition:

```fish
# Bad
set -l saw_g 0
if test $saw_g -eq 1
    ...
end

# Good
set -l saw_g false
if $saw_g
    ...
end
```

**Global variables in completion files** — completion files are sourced into
the user's shell, so a `set -g` leaks. Use a local set only on the found
path, then test with `set -q`:

```fish
# Bad
set -g __fish_dscl_ds_found 1

# Good
set -l ds_found
...
if set -q ds_found[1]
    ...
end
```

**Duplicated command-line parsing** — several helpers each re-walking the
tokens. Extract one parser and index it:

```fish
# Bad: __fish_dscl_datasource and __fish_dscl_command each walk the tokens.

# Good: one positional parser, thin accessors.
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

If a flag's behavior cannot be verified from the man page or `--help` output,
omit the completion or leave the description minimal and note the gap for the
reviewer — do not invent descriptions.
