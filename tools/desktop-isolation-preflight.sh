#!/usr/bin/env bash
# Only prepares/checks a disposable Desktop test root. NEVER launches, installs,
# updates, quits, or mutates a production DSH instance or global CLI.
set -euo pipefail
umask 077

usage() {
  printf 'Usage:\n  bash tools/desktop-isolation-preflight.sh prepare\n  bash tools/desktop-isolation-preflight.sh verify <test-root> <installed-desktop-bundled-dsh-absolute-path>\n' >&2
  exit 64
}
if [[ "$#" -eq 1 && "$1" == prepare ]]; then
  tempbase="${TMPDIR:-/tmp}"
  if [[ -z "$tempbase" ]]; then tempbase="/tmp"; fi
  root="$(mktemp -d "$tempbase/white-rice-farm-electron-XXXXXXXX")"
  chmod 700 "$root"
  for folder in dsh-home agents-home electron-user-data workspace xdg-config xdg-cache artifacts dist; do
    mkdir -p "$root/$folder"
    chmod 700 "$root/$folder"
  done
  printf 'DSH farm isolated test root; never mount or launch the normal DSH instance.\n' > "$root/.farm-desktop-isolated-root"
  printf 'Prepared private test directory: %s\n\n' "$root"
  printf 'For a verified isolated Desktop launch, use only these PRIVATE paths:\n'
  printf '  DSH_HOME=%s/dsh-home\n  DSH_AGENTS_HOME=%s/agents-home\n' "$root" "$root"
  printf '  XDG_CONFIG_HOME=%s/xdg-config\n  XDG_CACHE_HOME=%s/xdg-cache\n' "$root" "$root"
  printf '  workspace=%s/workspace\n  Electron userData target=%s/electron-user-data\n' "$root" "$root"
  printf '\nSTOP: this script does not assert that a packaged Desktop honors a userData override.\n'
  printf 'Official DEV launcher may honor DSH_DESKTOP_USER_DATA_DIR; packaged App must be proven isolated separately.\n'
  printf 'Do not run bundled CLI operations or start Desktop until the handoff isolation gates are confirmed.\n'
  exit 0
fi

if [[ "$#" -eq 3 && "$1" == verify ]]; then
  root="$2"
  cli="$3"
  [[ "$root" == /* ]] || { echo 'BLOCKED: test-root must be absolute' >&2; exit 2; }
  [[ "$cli" == /* ]] || { echo 'BLOCKED: CLI path must be absolute' >&2; exit 2; }
  [[ -f "$root/.farm-desktop-isolated-root" ]] || { echo 'BLOCKED: no test-root marker' >&2; exit 2; }
  [[ -d "$root/dsh-home" && -d "$root/agents-home" && -d "$root/electron-user-data" ]] || { echo 'BLOCKED: missing isolated directories' >&2; exit 2; }
  [[ -x "$cli" ]] || { echo 'BLOCKED: installed Desktop bundled CLI not executable' >&2; exit 2; }
  case "$cli" in
    */Contents/Resources/runtime/cli/bin/dsh|*/resources/runtime/cli/bin/dsh|*/Resources/runtime/cli/bin/dsh) ;;
    *) echo 'BLOCKED: CLI is not verified as an installed Desktop-bundled launcher' >&2; exit 2 ;;
  esac
  [[ "${DSH_HOME:-}" == "$root/dsh-home" ]] || { echo 'BLOCKED: DSH_HOME does not equal isolated path' >&2; exit 2; }
  [[ "${DSH_AGENTS_HOME:-}" == "$root/agents-home" ]] || { echo 'BLOCKED: DSH_AGENTS_HOME does not equal isolated path' >&2; exit 2; }
  profile="$root/dsh-home/profiles/desktop/package.json"
  [[ -f "$profile" ]] || { echo 'BLOCKED: Desktop has not initialized this private desktop profile' >&2; exit 2; }
  version="$("$cli" --version)"
  [[ "$version" == *0.2.2-rc.1* ]] || { echo "BLOCKED: expected Desktop bundled DSH v0.2.2-rc.1, got $version" >&2; exit 2; }
  printf 'PASSED preliminary path/profile/CLI checks for %s\n' "$root"
  echo 'MANDATORY MANUAL GATE: independently prove actual Electron userData, sessionData, process identity and runtime point inside this test root.'
  echo 'This script DOES NOT certify Desktop isolation or game installation.'
  exit 0
fi
usage
