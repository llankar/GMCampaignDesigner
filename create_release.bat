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

REM ===== Update version.txt (filevers/prodvers/FileVersion/ProductVersion) and commit/push before anything else =====
powershell -NoProfile -Command ^
  "$tag='%TAG%';" ^
  "$ver=($tag -replace '^v','').Trim();" ^
  "$tuple='(' + ($ver -split '\.' -join ', ') + ')';" ^
  "(Get-Content 'version.txt') " ^
  " -replace 'filevers=\([^)]*\)', ('filevers=' + $tuple)" ^
  " -replace 'prodvers=\([^)]*\)', ('prodvers=' + $tuple)" ^
  " -replace \"StringStruct\\('FileVersion',\\s*'[^']*'\\)\", \"StringStruct('FileVersion', '$ver')\"" ^
  " -replace \"StringStruct\\('ProductVersion',\\s*'[^']*'\\)\", \"StringStruct('ProductVersion', '$ver')\"" ^
  " | Set-Content -Encoding UTF8 'version.txt'"
if errorlevel 1 goto :err
git diff --quiet -- version.txt
if errorlevel 1 (
  echo [INFO] Updating version.txt to %TAG% and committing...
  git add version.txt || goto :err
  git commit -m "Bump version to %TAG%" || goto :err
  git push || goto :err
) else (
  echo [INFO] version.txt already at %TAG%; skipping commit.
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

REM ===== Update version.txt (filevers/prodvers/FileVersion/ProductVersion) and commit/push before tagging =====
powershell -NoProfile -Command ^
  "$tag='%TAG%';" ^
  "$ver=($tag -replace '^v','').Trim();" ^
  "$tuple='(' + ($ver -split '\.' -join ', ') + ')';" ^
  "(Get-Content 'version.txt') " ^
  " -replace 'filevers=\([^)]*\)', ('filevers=' + $tuple)" ^
  " -replace 'prodvers=\([^)]*\)', ('prodvers=' + $tuple)" ^
  " -replace \"StringStruct\\('FileVersion',\\s*'[^']*'\\)\", \"StringStruct('FileVersion', '$ver')\"" ^
  " -replace \"StringStruct\\('ProductVersion',\\s*'[^']*'\\)\", \"StringStruct('ProductVersion', '$ver')\"" ^
  " | Set-Content -Encoding UTF8 'version.txt'"
if errorlevel 1 goto :err
git diff --quiet -- version.txt
if errorlevel 1 (
  echo [INFO] Updating version.txt to %TAG% and committing...
  git add version.txt || goto :err
  git commit -m "Bump version to %TAG%" || goto :err
  git push || goto :err
) else (
  echo [INFO] version.txt already at %TAG%; skipping commit.
)

REM ===== Build release notes with commit list since previous tag =====
set "NOTES_FILE=docs/release-notes.md"
set "TMP_NOTES=%TEMP%\release-notes-%TAG%.md"
if exist "%TMP_NOTES%" del "%TMP_NOTES%"
if exist "%NOTES_FILE%" (
  copy /y "%NOTES_FILE%" "%TMP_NOTES%" >nul
) else (
  echo GMCampaignDesigner %TAG%>"%TMP_NOTES%"
)

REM Find previous tag (if any)
set "PREV_TAG="
for /f "usebackq delims=" %%t in (`git describe --tags --abbrev=0 "%TAG%^" 2^>nul`) do set "PREV_TAG=%%t"
if not defined PREV_TAG (
  for /f "usebackq delims=" %%t in (`git describe --tags --abbrev=0 HEAD^ 2^>nul`) do set "PREV_TAG=%%t"
)

echo.>>"%TMP_NOTES%"
if defined PREV_TAG (
  echo Commits since %PREV_TAG%:>>"%TMP_NOTES%"
  git log --pretty=format:"- %%s (%%h)" %PREV_TAG%..%TAG% >>"%TMP_NOTES%"
) else (
  echo Commits in %TAG%:>>"%TMP_NOTES%"
  git log --pretty=format:"- %%s (%%h)" %TAG% >>"%TMP_NOTES%"
)
echo.>>"%TMP_NOTES%"

REM ===== Git tag and push =====
git tag -f "%TAG%"
if errorlevel 1 goto :err
git push -f origin "%TAG%"
if errorlevel 1 goto :err

REM ===== If release exists: edit + clobber asset; else: create =====
gh release view "%TAG%" >nul 2>nul
if errorlevel 1 (
  echo [INFO] Release %TAG% not found. Creating...
  gh release create "%TAG%" "%ZIP%" --title "GMCampaignDesigner %TAG%" --notes-file "%TMP_NOTES%" || exit /b 1
) else (
  echo [INFO] Release %TAG% exists. Updating...
  gh release edit "%TAG%" --title "GMCampaignDesigner %TAG%" --notes-file "%TMP_NOTES%" || exit /b 1
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
