#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=/opt/noetrium
PACKAGE_ROOT="$(python -c 'from pathlib import Path; import noetrium_platform; print(Path(noetrium_platform.__file__).resolve().parent)')"
STATE_DIR="${PLATFORM_STATE_DIR:-/var/lib/noetrium}"

die() {
  echo "container-entrypoint: $*" >&2
  exit 2
}

doctor() {
  python --version
  python - <<'PY'
from importlib.metadata import version
import noetrium_platform

print(f"noetrium_platform_import={noetrium_platform.__name__}")
print(f"noetrium_platform_version={version('noetrium')}")
PY
  research --help >/dev/null
  noetrium-manage --help >/dev/null
  noetrium-architecture-gate --help >/dev/null 2>&1 || true
  mkdir -p "$STATE_DIR"
  test -w "$STATE_DIR"
  echo "platform_state_dir=$STATE_DIR writable=true"
}

minecraft_doctor() {
  doctor
  command -v java >/dev/null || die "minecraft provider requires Java"
  command -v node >/dev/null || die "minecraft provider requires Node"
  command -v npm >/dev/null || die "minecraft provider requires npm"
  java -version 2>&1 | head -n 1
  node --version
  npm --version
  local bridge="${MC_BRIDGE_DIR:-$PACKAGE_ROOT/environment/minecraft/providers/assets/mineflayer_bridge}"
  test -f "$bridge/package.json" || die "missing Mineflayer bridge package.json"
  MC_BRIDGE_DIR="$bridge" node - <<'JS'
const path = process.env.MC_BRIDGE_DIR
for (const name of ['mineflayer', 'mineflayer-pathfinder', 'mineflayer-pvp', 'vec3']) {
  const pkg = require(`${path}/node_modules/${name}/package.json`)
  console.log(`${name}=${pkg.version}`)
}
JS
  local data_dir="${MC_DATA_DIR:-/var/lib/minecraft}"
  mkdir -p "$data_dir"
  test -w "$data_dir"
  echo "minecraft_data_dir=$data_dir writable=true"
}

case "${1:-doctor}" in
  doctor)
    doctor
    ;;
  minecraft-doctor)
    minecraft_doctor
    ;;
  verify)
    doctor
    exec noetrium-architecture-gate
    ;;
  shell)
    shift
    if [[ $# -eq 0 ]]; then
      exec /bin/sh
    fi
    exec "$@"
    ;;
  *)
    die "unknown command '$1' (expected doctor, minecraft-doctor, verify or shell)"
    ;;
esac
