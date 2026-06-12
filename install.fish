#!/usr/bin/env fish
# Symlink every completion in completions/ into the user's fish completion
# directory, so the files in this repo are what fish actually loads (they
# shadow fish's auto-generated man-page completions, which are last on
# $fish_complete_path and have no subcommand awareness).
#
#   ./install.fish            install/refresh symlinks
#   ./install.fish --remove   remove symlinks that point into this repo

set -l repo (path resolve (status dirname))
set -l target $__fish_config_dir/completions

if contains -- --remove $argv
    set -l removed 0
    for link in $target/*.fish
        set -l dest (readlink $link 2>/dev/null); or continue
        if string match -q "$repo/completions/*" $dest
            rm $link
            set removed (math $removed + 1)
        end
    end
    echo "Removed $removed symlink(s) from $target"
    exit 0
end

mkdir -p $target
set -l count 0
for f in $repo/completions/*.fish
    ln -sf $f $target/(path basename $f)
    set count (math $count + 1)
end
echo "Linked $count completion(s) into $target"
echo "Open shells keep their cached completions — run 'exec fish' to refresh."
