# fish-macos-completions

Tab completions for [fish shell](https://fishshell.com/) covering macOS system
utilities that fish does not yet ship a completion for.

fish already bundles completions for many macOS tools (`launchctl`, `diskutil`,
`defaults`, `tmutil`, `plutil`, `mdfind`/`mdls`/`mdutil`, `caffeinate`,
`nvram`, `dscacheutil`, …). This repo fills the gaps — 21 system tools that
ship no completion — and is written to upstream-fish standard so each file can
drop into fish's `share/completions/` unchanged (tracking
[fish-shell#3525](https://github.com/fish-shell/fish-shell/issues/3525)).

## Tools covered

| Tool | Highlights |
|------|------------|
| `networksetup` | 90 verbs; live services / hardware ports / devices / locations / bonds / PPPoE |
| `scutil` | `--get/--set` prefs, `--dns`, `--proxy`, live `--nc` VPN services |
| `pmset` | power selectors, `-g` subargs, settings keywords, schedule/repeat events |
| `systemsetup` | `-get*/-set*` verb pairs; live timezones / startup disks |
| `dscl` | datasources, commands, live directory paths |
| `softwareupdate` | full flag set |
| `spctl` | assessment + Gatekeeper flags, `-t` types |
| `csrutil` | `status`/`enable`/`disable`/`clear`/`authenticated-root` |
| `sips` | image ops, property names, format values |
| `system_profiler` | live data types, detail levels, output formats |
| `pkgutil` | live package ids, receipt/forget/expand flags |
| `installer` | `-pkg` files, live `-target` volumes |
| `hdiutil` | image verbs + per-verb flags, live attached-image targets |
| `fdesetup` | FileVault subcommands + flags |
| `dseditgroup` | `-o` ops, `-t` record types, live groups |
| `sysadminctl` | user/secure-token/guest flags, live users |
| `profiles` | configuration-profile verbs + flags |
| `codesign` | sign/verify/display flags, live signing identities |
| `security` | ~50 keychain subcommands, live keychains |
| `osascript` | `-e`, `-l` language, script files |
| `screencapture` | capture-mode flags, `-t` formats |

Live enumeration uses only fast, unprivileged list commands, always guarded so
tab completion never hangs, hits the network, or prompts for a password.

## Install

**With the install script** — symlinks everything into fish's user completion
directory (`./install.fish --remove` undoes it):

```fish
./install.fish
```

**Manually** — symlink (or copy) into fish's completion path:

```fish
for f in completions/*.fish
    ln -sf (pwd)/$f ~/.config/fish/completions/(path basename $f)
end
```

**With [fisher](https://github.com/jorgebucaran/fisher):**

```fish
fisher install moonexpr/fish-macos-completions
```

New shells pick the completions up automatically; run `exec fish` to refresh an
open one.

## Testing

```fish
fish tests/check.fish        # all tools
fish tests/check.fish pmset  # one tool
```

For each `completions/<tool>.fish` the harness asserts it parses (`fish -n`) and
that `complete -C "<tool> "` / `"<tool> -"` yields real candidates rather than
filename fallback.

## Conventions

See [`PROJECT.md`](PROJECT.md). In short: helpers namespaced `__fish_<tool>_*`,
every subcommand/verb carries a man-page-grounded description, no invented
flags, and live enumeration only via fast unprivileged commands.

## License

These files are intended for upstream contribution to fish-shell and follow its
conventions; treat them as available under fish-shell's license terms.
