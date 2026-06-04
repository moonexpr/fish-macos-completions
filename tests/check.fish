#!/usr/bin/env fish
# check.fish — parse + smoke harness for completions/*.fish
#
# For each completion file:
#   V1 parse  — `fish -n` exits 0
#   V2 smoke  — `complete -C "<tool> "` yields ≥1 candidate, and the candidate
#               set is not pure filename fallback (heuristic: at least one
#               candidate is not a path that exists in the cwd)
#
# Usage: fish tests/check.fish [tool ...]   (no args = all)
# Exit:  0 if all pass, 1 otherwise.

set -l root (path resolve (status dirname)/..)
set -l compdir $root/completions

set -l names
if set -q argv[1]
    set names $argv
else
    for f in $compdir/*.fish
        set names $names (path change-extension '' (path basename $f))
    end
end

set -l fails 0
for tool in $names
    set -l file $compdir/$tool.fish
    if not test -f $file
        echo "MISSING  $tool ($file)"
        set fails (math $fails + 1)
        continue
    end

    # V1: parse
    if not fish -n $file
        echo "FAIL[V1] $tool — does not parse"
        set fails (math $fails + 1)
        continue
    end

    # V2: smoke — load this file's completions in isolation and ask for
    # candidates. Probe both grammars: `<tool> ` (subcommand tools) and
    # `<tool> -` (single-dash-verb / flag tools). Pass if either yields a
    # candidate set that is not pure filename fallback.
    set -l out (fish --no-config -c "source $file 2>/dev/null; complete -C '$tool '" 2>/dev/null)
    set -l outdash (fish --no-config -c "source $file 2>/dev/null; complete -C '$tool -'" 2>/dev/null)
    if test (count $out) -eq 0; and test (count $outdash) -eq 0
        echo "FAIL[V2] $tool — no completions offered"
        set fails (math $fails + 1)
        continue
    end
    # heuristic: a real (non-filename) candidate in either probe
    set -l nonfile 0
    for line in $out $outdash
        set -l cand (string split -f1 \t -- $line)
        # dashed candidates and non-existent paths are "real" (not cwd files)
        if string match -q -- '-*' $cand; or not test -e $cand
            set nonfile 1
        end
    end
    if test $nonfile -eq 0
        echo "FAIL[V2] $tool — only filename fallback, no real candidates"
        set fails (math $fails + 1)
        continue
    end

    echo "PASS     $tool ("(count $out)"+"(count $outdash)" candidates)"
end

if test $fails -gt 0
    echo "—— $fails failure(s)"
    exit 1
end
echo "—— all green"
