# Build macOS

## Build locally

Run the macOS release script from the repository root:

```bash
bash scripts/create_release_macos.sh
```

The script produces a zip under `release/` with the pattern `release/*.zip`, using the naming
`GMCampaignDesigner-<version>-macos.zip` (for example, `GMCampaignDesigner-1.2.3-macos.zip`).
The `<version>` is resolved from `version.txt` when available, then falls back to the latest git tag,
and finally defaults to `dev`.

## Run the GitHub Actions workflow manually

1. Open the **Actions** tab in GitHub.
2. Select the **Build macOS Release** workflow.
3. Click **Run workflow** and confirm the branch.

## Download the macOS artifact

After the workflow completes, open the workflow run summary and find the **Artifacts** section.
Download the `macos-release` artifact; it contains the zip produced from `release/*.zip`, with the
same naming convention (`GMCampaignDesigner-<version>-macos.zip`).
