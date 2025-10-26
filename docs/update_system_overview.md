# Automatic Update System

This document explains how GMCampaignDesigner now checks for new releases, how the download/apply flow works, and what steps are needed to publish an update that the application can consume automatically.

## Runtime behaviour

- **Startup polling** – When `MainWindow` launches it schedules `_queue_update_check`. The first poll in each application session is forced (ignoring the configured interval) so newly published releases are detected immediately. Subsequent polls honour the `[Updates]` section in `config/config.ini` and spawn a background thread. The worker calls `modules.helpers.update_helper.check_for_update`, compares the installed version from `version.txt` with the latest GitHub Release, and prompts the user only if a newer asset is available.
- **User prompt** – The dialog summarises the target version and truncates release notes to a readable snippet. Declining closes the prompt; accepting triggers the download workflow.
- **Download + staging** – `_run_progress_task` hosts the progress dialog while `update_helper.prepare_staging_area` streams the zip asset into a temporary folder and extracts it. Progress messages update the modal without blocking Tkinter’s event loop.
- **Applying the update** – Once staged, `update_helper.launch_installer` starts `scripts/apply_update.py`. That helper waits for the main process to exit, copies the staged payload into the install directory, skips preserved paths such as `Campaigns/` and `config/config.ini`, optionally restarts the executable, and removes the temporary staging directory.

## Configuration keys (`config/config.ini`)

```
[Updates]
enabled = true
channel = stable
asset_name =
check_interval_hours = 24
last_check =
```

- `enabled` – Toggle automatic polling. If set to `false`, no background check runs.
- `channel` – `stable` ignores GitHub pre-releases; set to `prerelease` to allow them.
- `asset_name` – Optional exact asset name to download when a release exposes multiple files.
- `check_interval_hours` – Minimum delay between polls. The default is once per day.
- `last_check` – Timestamp persisted after a successful poll to enforce the interval.

## Publishing a release for the updater

1. **Update version metadata**
   ```bash
   nano version.txt              # bump FileVersion/ProductVersion values
   ```

2. **Build the distributable**
   ```bash
   pyinstaller --noconfirm main_window.spec
   ```

3. **Create the release archive**
   ```bash
   cd dist
   zip -r ../RPGCampaignManager-vX.Y.Z.zip RPGCampaignManager
   cd ..
   ```
   *(On Windows use `powershell Compress-Archive -Path dist\RPGCampaignManager\* -DestinationPath RPGCampaignManager-vX.Y.Z.zip`.)*

4. **Tag the commit and push the tag**
   ```bash
   TAG=vX.Y.Z
   git tag "$TAG"
   git push origin "$TAG"
   ```

5. **Publish the GitHub Release**
   ```bash
   gh release create "$TAG" RPGCampaignManager-vX.Y.Z.zip \
     --title "GMCampaignDesigner $TAG" \
     --notes "Summary of changes"
   ```
   The updater queries GitHub’s Releases API and downloads the asset via its `browser_download_url`, so ensure the archive is attached to the release.

6. **Verify** – Open the release page in a browser and copy the asset link. Launching the application should now prompt for the update when the installed version is older than the release tag.

## Safety considerations

- `scripts/apply_update.py` preserves user-managed content directories by default and will refuse to proceed if the staging payload or install root is missing.
- Errors during HTTP requests, extraction, or helper launch surface through the existing logging infrastructure, and the UI will display an error message if the worker raises an exception.
- The helper waits up to 15 minutes for the main process to exit; adjust `--wait-timeout` if larger installations need more time for shutdown scripts.

This pipeline keeps release management simple—package the PyInstaller output, attach it to a GitHub Release, and the application will discover and install the update without touching campaign data.
