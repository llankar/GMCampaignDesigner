@echo off
setlocal enabledelayedexpansion

REM ===== Usage =====
if "%~1"=="" (
  echo Usage: %~nx0 TAG
  exit /b 1
)
set "TAG=%~1"

REM ===== Preconditions (optional but helpful) =====
where gh >nul 2>nul
if errorlevel 1 (
  echo [ERROR] GitHub CLI ^(gh^) not found in PATH. Install from https://cli.github.com/ and run "gh auth login".
  exit /b 1
)

REM ===== Build =====
pyinstaller --noconfirm --clean main_window.spec
if errorlevel 1 goto :err

REM If copy_dist.bat prepares your dist folder, CALL it so control returns to this script
call copy_dist.bat
if errorlevel 1 goto :err

set "ZIP=RPGCampaignManager-%TAG%.zip"

REM ===== Zip the build =====
powershell -NoProfile -Command "Compress-Archive -Path 'dist\RPGCampaignManager\*' -DestinationPath '%ZIP%' -Force"
if errorlevel 1 goto :err

REM ===== Git tag and push =====
git tag -f "%TAG%"
if errorlevel 1 goto :err
git push -f origin "%TAG%"
if errorlevel 1 goto :err

REM ===== If release exists: edit + clobber asset; else: create =====
gh release view "%TAG%" >nul 2>nul
if errorlevel 1 (
  echo [INFO] Release %TAG% not found. Creating...
  gh release create "%TAG%" "%ZIP%" --title "GMCampaignDesigner %TAG%" --notes-file "docs/release-notes.md" || exit /b 1
) else (
  echo [INFO] Release %TAG% exists. Updating...
  gh release edit "%TAG%" --title "GMCampaignDesigner %TAG%" --notes-file "docs/release-notes.md" || exit /b 1
  gh release upload "%TAG%" "%ZIP%" --clobber || exit /b 1
)

echo "[OK] Release %TAG% is up to date."
if errorlevel 1 goto :err

echo.
echo "[OK] Release %TAG% created successfully."
goto :eof

:err
echo.
echo "[FAILED] ErrorLevel=%ERRORLEVEL%"
exit /b %ERRORLEVEL%
