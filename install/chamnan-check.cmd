@echo off
rem Does this Windows machine have what chamnan needs, and what installs it if not.
rem
rem The batch twin of install/chamnan-check.sh, and deliberately much smaller. It exists for one
rem case: native cmd.exe or PowerShell with no Git Bash and no WSL, where the .sh cannot run. If
rem you have either of those, run the .sh instead -- it detects more and explains more.
rem
rem HONESTY NOTE, and it is the reason this file is as short as it is: it was written on macOS,
rem where no developer machine can run it. It IS executed on Windows now -- `.github/workflows/
rem tests.yml` runs it on every windows-latest leg ("The preflight runs where there is no POSIX
rem shell") -- so the claim this line carried until 2026-09-08, that no Windows machine had ever
rem run it, was disproven by log output already in hand (R10 agent 1). What has not changed is why
rem it is written this way: it uses only
rem `where`, `if errorlevel` and `echo` -- the batch constructs least likely to be wrong -- and it
rem installs nothing by itself. If it misbehaves, the two commands it prints are the whole content
rem and can be run by hand.
rem
rem     install\chamnan-check.cmd

echo chamnan - checking this machine
echo.

set FOUNDPY=
where py >nul 2>nul
if not errorlevel 1 set FOUNDPY=py -3
if "%FOUNDPY%"=="" (
    where python >nul 2>nul
    if not errorlevel 1 set FOUNDPY=python
)

if "%FOUNDPY%"=="" (
    echo   python      NOT FOUND
) else (
    echo   python      found as: %FOUNDPY%
    %FOUNDPY% -V
    echo   chamnan needs 3.8 or newer. Check the line above.
)

where git >nul 2>nul
if errorlevel 1 (
    echo   git         NOT FOUND
) else (
    echo   git         found
)

echo.
echo   If either is missing, this installs both:
echo.
echo       winget install --id Python.Python.3.13 -e
echo       winget install --id Git.Git -e
echo.
echo   Then open a NEW terminal so PATH is picked up, and run this again.
