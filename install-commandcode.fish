#!/usr/bin/env fish
set -l repo_url https://github.com/phandinhdoc-spec/cmd-orchestrator.git
set -l branch (set -q CMD_ORCHESTRATOR_BRANCH; and echo $CMD_ORCHESTRATOR_BRANCH; or echo feature/commandcode-native-v2)
set -l target $HOME/.commandcode/cmd-orchestrator-src

mkdir -p $HOME/.commandcode

if test -d $target/.git
    git -C $target fetch origin
    git -C $target checkout $branch
    git -C $target pull --ff-only origin $branch
else
    git clone --branch $branch --single-branch $repo_url $target
end

if not test -f $target/cmd.py
    echo "ERROR: $target/cmd.py not found after checkout of $branch"
    exit 1
end

mkdir -p $HOME/.local/bin
printf '%s\n' '#!/usr/bin/env fish' 'python3 '$target'/cmd.py $argv' > $HOME/.local/bin/cmd-orchestrator
chmod +x $HOME/.local/bin/cmd-orchestrator
fish_add_path $HOME/.local/bin

echo "Installed cmd-orchestrator from branch: $branch"
echo "Source: $target"
echo "Test: cmd-orchestrator --help"
