#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

export PYTHONHASHSEED="${PYTHONHASHSEED:-0}"
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1704067200}"

python_bin="${PYTHON:-python3}"
build_root="$project_root/.pyinstaller"
launcher_dir="$build_root/launchers"
build_dir="$build_root/build"
spec_dir="$build_root/spec"
dist_dir="$project_root/dist"

echo "Preparing clean PyInstaller build directories..."
rm -rf "$build_root" "$dist_dir"
mkdir -p "$launcher_dir" "$build_dir" "$spec_dir" "$dist_dir"

cat > "$launcher_dir/veyralock_cli_launcher.py" <<'PY'
from veyralock.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
PY

cat > "$launcher_dir/veyralock_gui_launcher.py" <<'PY'
from veyralock.gui import main

if __name__ == "__main__":
    raise SystemExit(main())
PY

echo "Installing build dependencies..."
"$python_bin" -m pip install --upgrade pip
"$python_bin" -m pip install -e ".[dev]" pyinstaller build

echo "Building CLI executable..."
"$python_bin" -m PyInstaller \
    --noconfirm \
    --clean \
    --onefile \
    --name veyralock \
    --distpath "$dist_dir" \
    --workpath "$build_dir" \
    --specpath "$spec_dir" \
    "$launcher_dir/veyralock_cli_launcher.py"

echo "Building GUI executable..."
"$python_bin" -m PyInstaller \
    --noconfirm \
    --clean \
    --onefile \
    --windowed \
    --name veyralock-gui \
    --distpath "$dist_dir" \
    --workpath "$build_dir" \
    --specpath "$spec_dir" \
    "$launcher_dir/veyralock_gui_launcher.py"

echo "Build complete. Artifacts are in dist/"
