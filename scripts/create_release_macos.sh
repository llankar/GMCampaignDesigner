#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[%s] %s\n' "$(date +'%Y-%m-%d %H:%M:%S')" "$*"
}

fail() {
  printf '[ERROR] %s\n' "$*" >&2
  exit 1
}

ensure_repo_root() {
  local repo_root
  repo_root="$(git rev-parse --show-toplevel)"
  cd "$repo_root"
}

extract_version_from_file() {
  local version_file="$1"
  local version

  version="$(
    python3 - "$version_file" <<'PY'
import re
import sys

version_file = sys.argv[1]
pattern = re.compile(r"StringStruct\('(FileVersion|ProductVersion)',\s*'([^']+)'\)")

with open(version_file, 'r', encoding='utf-8', errors='ignore') as handle:
    for line in handle:
        match = pattern.search(line)
        if match:
            print(match.group(2))
            sys.exit(0)
PY
  )"

  if [[ -n "$version" ]]; then
    printf '%s\n' "$version"
  fi
}

resolve_version() {
  local version_file="version.txt"
  local version=""

  if [[ -f "$version_file" ]]; then
    version="$(extract_version_from_file "$version_file" || true)"
  fi

  if [[ -z "$version" ]]; then
    version="$(git describe --tags --abbrev=0 2>/dev/null || true)"
  fi

  if [[ -z "$version" ]]; then
    version="dev"
  fi

  printf '%s\n' "$version"
}

resolve_internal_assets_dir() {
  local dist_root="dist"
  local assets_dir

  if [[ ! -d "$dist_root" ]]; then
    fail "Expected dist output not found under '$dist_root'."
  fi

  assets_dir="$(
    find "$dist_root" -type d \( \
      -path "*/_internal/assets" \
      -o -path "*/Contents/Resources/_internal/assets" \
      -o -path "*/Contents/Resources/assets" \
      -o -path "*/assets" \
    \) -print | head -n 1
  )"

  if [[ -n "$assets_dir" ]]; then
    printf '%s\n' "$assets_dir"
    return
  fi

  fail "Expected assets directory not found in dist output. Searched for '_internal/assets' or 'assets' within '$dist_root'."
}

clean_dist() {
  local assets_dir
  local generated_dir
  local portraits_dir

  assets_dir="$(resolve_internal_assets_dir)"
  generated_dir="$assets_dir/generated"
  portraits_dir="$assets_dir/portraits"

  [[ -d "$generated_dir" ]] || fail "Missing generated assets directory: $generated_dir"
  [[ -d "$portraits_dir" ]] || fail "Missing portraits assets directory: $portraits_dir"

  log "Cleaning generated assets in $generated_dir"
  rm -rf "$generated_dir"/*

  log "Cleaning portraits assets in $portraits_dir"
  rm -rf "$portraits_dir"/*
}

resolve_dist_roots() {
  local dist_root="dist"
  local candidate_root

  if [[ -d "$dist_root" ]]; then
    local entry
    for entry in "$dist_root"/*; do
      [[ -d "$entry" ]] || continue
      local app_bundle
      for app_bundle in "$entry"/*.app; do
        if [[ -d "$app_bundle/Contents/Resources" ]]; then
          printf '%s\n' "$app_bundle/Contents/Resources"
          return
        fi
      done
    done

    local legacy_bundle
    for legacy_bundle in "$dist_root"/*.app; do
      if [[ -d "$legacy_bundle/Contents/Resources" ]]; then
        printf '%s\n' "$legacy_bundle/Contents/Resources"
        return
      fi
    done

    candidate_root="$(
      find "$dist_root" -mindepth 1 -maxdepth 2 -type d \( \
        -path "*/_internal" -o -path "*/assets" \
      \) -print | head -n 1
    )"
    if [[ -n "$candidate_root" ]]; then
      printf '%s\n' "$(dirname "$candidate_root")"
      return
    fi
  fi

  fail "Expected dist output not found under '$dist_root'."
}

copy_checked_dir() {
  local src="$1"
  local dest="$2"

  [[ -d "$src" ]] || fail "Source directory missing: $src"
  mkdir -p "$dest"
  cp -R "$src" "$dest"
}

copy_checked_file() {
  local src="$1"
  local dest="$2"

  [[ -f "$src" ]] || fail "Source file missing: $src"
  mkdir -p "$dest"
  cp "$src" "$dest"
}

copy_dist() {
  local dist_root
  local internal_root

  dist_root="$(resolve_dist_roots)"
  if [[ -d "$dist_root/_internal" ]]; then
    internal_root="$dist_root/_internal"
  else
    internal_root="$dist_root"
  fi

  log "Copying assets to $dist_root"
  copy_checked_dir "assets" "$dist_root"

  log "Copying modules to $dist_root"
  copy_checked_dir "modules" "$dist_root"

  log "Copying config to $dist_root"
  copy_checked_dir "config" "$dist_root"

  log "Copying docs to $dist_root"
  copy_checked_dir "docs" "$dist_root"

  log "Copying modules to $internal_root"
  copy_checked_dir "modules" "$internal_root"

  log "Copying version.txt to $dist_root"
  copy_checked_file "version.txt" "$dist_root"
  if [[ "$internal_root" != "$dist_root" ]]; then
    log "Copying version.txt to $internal_root"
    copy_checked_file "version.txt" "$internal_root"
  fi
}

build_pyinstaller() {
  local spec_file="main_window_macos.spec"

  if [[ ! -f "$spec_file" ]]; then
    spec_file="main_window.spec"
  fi

  pyinstaller --noconfirm --clean "$spec_file"
}

create_release_zip() {
  local version="$1"
  local release_dir="release"
  local zip_name="GMCampaignDesigner-${version}-macos.zip"
  local dist_root
  local app_bundle
  local app_found=""

  # Naming choice: GMCampaignDesigner matches the repository/project name.
  mkdir -p "$release_dir"

  if [[ -d "dist" ]]; then
    for app_bundle in dist/*/*.app dist/*.app; do
      [[ -d "$app_bundle" ]] || continue
      log "Packaging macOS app bundle with ditto"
      ditto -c -k --sequesterRsrc --keepParent "$app_bundle" "$release_dir/$zip_name"
      app_found="yes"
      break
    done
  fi

  if [[ -n "$app_found" ]]; then
    return
  fi

  if [[ -d "dist/RPGCampaignManager" ]]; then
    dist_root="dist/RPGCampaignManager"
  elif [[ -d "dist" ]]; then
    for dist_root in dist/*; do
      [[ -d "$dist_root" ]] || continue
      break
    done
  fi

  if [[ -n "${dist_root:-}" && -d "$dist_root" ]]; then
    log "Packaging dist folder with zip"
    (cd "$dist_root" && zip -r "../$release_dir/$zip_name" .)
    return
  fi

  # If we reach here, we expected a .app but it was not produced.
  fail "No .app bundle or dist folder found to package. Ensure PyInstaller output is available."
}

main() {
  local version

  ensure_repo_root

  log "Resolving version"
  version="$(resolve_version)"
  log "Using version: $version"

  log "Building PyInstaller bundle"
  build_pyinstaller

  log "Copying dist assets"
  copy_dist

  log "Cleaning dist artifacts"
  clean_dist

  log "Creating release zip"
  create_release_zip "$version"

  log "Release package created successfully"
}

main "$@"
