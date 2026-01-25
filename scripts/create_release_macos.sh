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
    sed -nE "s/.*StringStruct\('(?:FileVersion|ProductVersion)',\s*'([^']+)'\).*/\1/p" "$version_file" \
      | head -n 1
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
  local dist_root="dist/RPGCampaignManager"
  local app_resources="dist/RPGCampaignManager.app/Contents/Resources"

  if [[ -d "$dist_root/_internal/assets" ]]; then
    printf '%s\n' "$dist_root/_internal/assets"
    return
  fi

  if [[ -d "$app_resources/_internal/assets" ]]; then
    # PyInstaller can emit a .app bundle on macOS; use Resources for its internal payload.
    printf '%s\n' "$app_resources/_internal/assets"
    return
  fi

  fail "Expected internal assets directory not found in dist output. Looked for '$dist_root/_internal/assets' or '$app_resources/_internal/assets'."
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
  local dist_root="dist/RPGCampaignManager"
  local app_resources="dist/RPGCampaignManager.app/Contents/Resources"

  if [[ -d "$dist_root" ]]; then
    printf '%s\n' "$dist_root"
    return
  fi

  if [[ -d "$app_resources" ]]; then
    # macOS .app bundle output: treat Resources as the root for bundled content.
    printf '%s\n' "$app_resources"
    return
  fi

  fail "Expected dist output not found. Looked for '$dist_root' or '$app_resources'."
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
  internal_root="$dist_root/_internal"

  [[ -d "$internal_root" ]] || fail "Internal dist directory missing: $internal_root"

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

  log "Copying version.txt to $dist_root and $internal_root"
  copy_checked_file "version.txt" "$dist_root"
  copy_checked_file "version.txt" "$internal_root"
}

build_pyinstaller() {
  # Assumption: main_window.spec is the macOS PyInstaller spec file.
  pyinstaller --noconfirm --clean main_window.spec
}

create_release_zip() {
  local version="$1"
  local release_dir="release"
  local zip_name="GMCampaignDesigner-${version}-macos.zip"
  local app_bundle="dist/RPGCampaignManager.app"
  local dist_root

  # Naming choice: GMCampaignDesigner matches the repository/project name.
  mkdir -p "$release_dir"

  if [[ -d "$app_bundle" ]]; then
    log "Packaging macOS app bundle with ditto"
    ditto -c -k --sequesterRsrc --keepParent "$app_bundle" "$release_dir/$zip_name"
    return
  fi

  dist_root="dist/RPGCampaignManager"
  if [[ -d "$dist_root" ]]; then
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

  log "Cleaning dist artifacts"
  clean_dist

  log "Building PyInstaller bundle"
  build_pyinstaller

  log "Copying dist assets"
  copy_dist

  log "Creating release zip"
  create_release_zip "$version"

  log "Release package created successfully"
}

main "$@"
