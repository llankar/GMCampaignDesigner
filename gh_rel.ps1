$repo = 'llankar/GMCampaignDesigner'

$json = gh release list --repo $repo --limit 100 --json tagName,name,isDraft,publishedAt 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host 'GitHub CLI error:' -ForegroundColor Red
    Write-Host $json
    Read-Host 'Press Enter to close'
    exit 1
}

try {
    $rawReleases = $json | ConvertFrom-Json
}
catch {
    Write-Host 'GitHub CLI did not return valid JSON:' -ForegroundColor Red
    Write-Host $json
    Read-Host 'Press Enter to close'
    exit 1
}

$releases = @(
    $rawReleases | ForEach-Object {
        [PSCustomObject]@{
            Tag         = $_.tagName
            Name        = $_.name
            Draft       = $_.isDraft
            PublishedAt = $_.publishedAt
        }
    }
)

if ($releases.Count -eq 0) {
    Write-Host "No releases found in $repo." -ForegroundColor Yellow
    Read-Host 'Press Enter to close'
    exit 0
}

$selected = $releases | Out-GridView -Title 'Select releases to delete - Ctrl+Click for multiple selection' -PassThru

if (-not $selected) {
    Write-Host 'No release selected.'
    exit 0
}

Write-Host ''
Write-Host 'Selected releases:' -ForegroundColor Yellow
$selected | Format-Table Tag, Name, Draft, PublishedAt -AutoSize

$confirmation = Read-Host 'Type DELETE to confirm'

if ($confirmation -cne 'DELETE') {
    Write-Host 'Operation cancelled.'
    exit 0
}

foreach ($release in $selected) {
    $tag = $release.Tag

    Write-Host "Deleting release: $tag" -ForegroundColor Cyan

    gh release delete $tag --repo $repo --yes

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to delete: $tag" -ForegroundColor Red
    }
    else {
        Write-Host "Deleted: $tag" -ForegroundColor Green
    }
}

Write-Host ''
Write-Host 'Finished.' -ForegroundColor Green