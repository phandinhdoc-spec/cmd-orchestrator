#!/usr/bin/env fish
set -l repo_url https://github.com/phandinhdoc-spec/cmd-orchestrator.git
set -l target $HOME/.commandcode/cmd-orchestrator-src
mkdir -p $HOME/.commandcode
if test -d $target/.git
    git -C $target fetch origin
    git -C $target checkout main
    git -C $target pull --ff-only origin main
else
    git clone $repo_url $target
end
mkdir -p $HOME/.local/bin
printf '%s\n' '#!/usr/bin/env fish' 'python3 '$target'/cmd.py $argv' > $HOME/.local/bin/cmd-orchestrator
chmod +x $HOME/.local/bin/cmd-orchestrator
fish_add_path $HOME/.local/bin
echo "Installed: cmd-orchestrator"
echo "Test: cmd-orchestrator --help"
