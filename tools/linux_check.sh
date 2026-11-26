#!/bin/sh
# Unprivileged Linux test run (no sudo, no system packages): a venv without pip plus unpacked wheels.
# Usage: PBD_REPO=/path/to/checkout PBD_WHEELS=/path/to/linux-wheels sh tools/linux_check.sh tests -rs
set -e
REPO=${PBD_REPO:?set PBD_REPO to the checkout path as seen from Linux}
WHEELS=${PBD_WHEELS:?set PBD_WHEELS to a folder of Linux wheels (see docs/install.md)}
WORK=$HOME/pbd-linux-qual
rm -rf "$WORK" && mkdir -p "$WORK"
mkdir -p "$WORK/src-tree" && cd "$REPO" && git ls-files -co --exclude-standard -z | tar --null -T - -cf - | tar -x -C "$WORK/src-tree"
python3 -m venv --without-pip "$WORK/venv"
SITE=$("$WORK/venv/bin/python" -c "import sysconfig;print(sysconfig.get_paths()['purelib'])")
for w in "$WHEELS"/*.whl; do "$WORK/venv/bin/python" -c "import zipfile,sys;zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$w" "$SITE"; done
cd "$WORK/src-tree"
uname -a
"$WORK/venv/bin/python" --version
"$WORK/venv/bin/python" -m pytest --version
PYTHONPATH=src:. "$WORK/venv/bin/python" -m pytest -q -p no:cacheprovider -m "not playwright" "$@" 2>&1 | tail -15
