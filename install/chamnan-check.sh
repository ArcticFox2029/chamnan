#!/bin/sh
# Does this machine have what chamnan needs, and if not, what is the one command that fixes it?
#
# POSIX sh on purpose, and NOT Python. Every other file in this plugin is Python, which makes this
# the one check that cannot be written in it: a machine with no Python cannot run the script that
# says it has no Python. `sh` is on every Linux, every macOS, and inside WSL and Git Bash.
#
# It REPORTS by default and installs only when asked. `--install` runs the package manager command
# printed below, which needs root and changes the machine -- that is the user's call, not a
# plugin's, and a plugin that installs system packages the first time it runs is a plugin nobody
# should trust. The command is printed either way so it can be read before it is run.
#
#     sh install/chamnan-check.sh              report only
#     sh install/chamnan-check.sh --install    run the fix as well
#
# Exit codes: 0 everything present, 1 something missing.

MIN_MAJOR=3
MIN_MINOR=8

WANT_INSTALL=0
[ "$1" = "--install" ] && WANT_INSTALL=1

say() { printf '%s\n' "$*"; }

# --- which system is this ------------------------------------------------------------------
# `uname -s` rather than anything cleverer: it is in POSIX, and the three answers that matter are
# Darwin, Linux and one of MINGW*/MSYS*/CYGWIN* for Git Bash on Windows.
OS="$(uname -s 2>/dev/null || echo unknown)"
case "$OS" in
    Darwin) FAMILY=macos ;;
    Linux)  FAMILY=linux ;;
    MINGW*|MSYS*|CYGWIN*) FAMILY=windows ;;
    *)      FAMILY=unknown ;;
esac

# WSL reports Linux and is treated as Linux, which is right: its filesystem, its package manager
# and its Python are Linux's. Reported separately only so the user knows the script saw it.
WSL=""
if [ "$FAMILY" = linux ] && grep -qi microsoft /proc/version 2>/dev/null; then
    WSL=" (WSL)"
fi

# --- which package manager, and the exact command ------------------------------------------
# Detected by which binary exists rather than by reading /etc/os-release: a derivative names
# itself something the list would not have, while `apt-get` either exists or does not.
PKG_CMD=""
PKG_NAME=""
if [ "$FAMILY" = macos ]; then
    if command -v brew >/dev/null 2>&1; then
        PKG_CMD="brew install python git"; PKG_NAME="Homebrew"
    else
        # NOT `xcode-select --install`. It installs git, and the python it brings is whatever
        # Apple ships -- which on an older macOS is below the floor this script is checking for,
        # so it would report success and leave the machine exactly as unusable as before.
        PKG_CMD='/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" && brew install python git'
        PKG_NAME="Homebrew, which is not installed yet"
    fi
elif [ "$FAMILY" = linux ]; then
    if command -v apt-get >/dev/null 2>&1; then
        PKG_CMD="sudo apt-get update && sudo apt-get install -y python3 git"; PKG_NAME="apt"
    elif command -v dnf >/dev/null 2>&1; then
        PKG_CMD="sudo dnf install -y python3 git"; PKG_NAME="dnf"
    elif command -v yum >/dev/null 2>&1; then
        PKG_CMD="sudo yum install -y python3 git"; PKG_NAME="yum"
    elif command -v pacman >/dev/null 2>&1; then
        PKG_CMD="sudo pacman -S --noconfirm python git"; PKG_NAME="pacman"
    elif command -v apk >/dev/null 2>&1; then
        PKG_CMD="apk add --no-cache python3 git"; PKG_NAME="apk"
    elif command -v zypper >/dev/null 2>&1; then
        PKG_CMD="sudo zypper install -y python3 git"; PKG_NAME="zypper"
    fi
elif [ "$FAMILY" = windows ]; then
    if command -v winget >/dev/null 2>&1; then
        PKG_CMD="winget install --id Python.Python.3.13 -e && winget install --id Git.Git -e"
        PKG_NAME="winget"
    elif command -v choco >/dev/null 2>&1; then
        PKG_CMD="choco install -y python git"; PKG_NAME="Chocolatey"
    fi
fi

# --- python -----------------------------------------------------------------------------------
# Three names, in the order that gets the right answer most often. `python3` first because that is
# what the shebangs say; `py -3` last because it is Windows-only and launches whatever is newest.
#
# 🐛 [2026-09-07] Windows ships a `python3.exe`/`python.exe` "App Execution Alias" stub when no real
# Python is installed: it is ON PATH, it exists, and running it prints an error and opens the Store.
# This loop committed to the first name that existed and never asked whether it WORKED, so the
# stub's error text parsed to version "was" — which fails the numeric test below and reported
# "python was — too old". A brand-new Windows user was told to upgrade a Python they do not have,
# at the exact moment they most need the right diagnosis (R10 agent 1).
#
# So a candidate has to answer `-V` successfully before it is accepted, and the loop keeps looking
# otherwise. `python3` first because that is what the shebangs say; `py -3` last because it is
# Windows-only and launches whatever is newest.
PY=""
for candidate in python3 python py; do
    command -v "$candidate" >/dev/null 2>&1 || continue
    if [ "$candidate" = py ]; then
        "$candidate" -3 -V >/dev/null 2>&1 || continue
        PY="$candidate -3"
    else
        "$candidate" -V >/dev/null 2>&1 || continue
        PY="$candidate"
    fi
    break
done

PY_OK=0
PY_VER=""
if [ -n "$PY" ]; then
    # Version out of `-V` rather than by running code: the point of this script is to work when
    # running Python code is the thing in question.
    PY_VER="$($PY -V 2>&1 | awk '{print $2}')"
    MAJ="$(printf '%s' "$PY_VER" | cut -d. -f1)"
    MIN="$(printf '%s' "$PY_VER" | cut -d. -f2)"
    case "$MAJ$MIN" in
        ''|*[!0-9]*) MAJ=0; MIN=0 ;;
    esac
    if [ "$MAJ" -gt "$MIN_MAJOR" ] 2>/dev/null; then
        PY_OK=1
    elif [ "$MAJ" -eq "$MIN_MAJOR" ] 2>/dev/null && [ "$MIN" -ge "$MIN_MINOR" ] 2>/dev/null; then
        PY_OK=1
    fi
fi

GIT_OK=0
command -v git >/dev/null 2>&1 && GIT_OK=1

# --- report -------------------------------------------------------------------------------
say "chamnan — checking this machine"
say ""
say "  system      $FAMILY$WSL"
if [ "$PY_OK" = 1 ]; then
    say "  python      $PY_VER  ($PY)"
else
    if [ -n "$PY" ] && [ "$MAJ" != 0 ]; then
        say "  python      $PY_VER — too old, chamnan needs $MIN_MAJOR.$MIN_MINOR or newer"
    elif [ -n "$PY" ]; then
        # It answered `-V` but not with a version. Whatever it is, "too old" is the wrong advice
        # and the number it would quote is not a number.
        say "  python      found on PATH as \`$PY\` but it does not report a version"
        say "              — install a real Python; on Windows, disable the Store alias in"
        say "                Settings > Apps > App execution aliases if that is what is there"
    else
        say "  python      NOT FOUND"
    fi
fi
if [ "$GIT_OK" = 1 ]; then
    say "  git         $(git --version 2>/dev/null | awk '{print $3}')"
else
    say "  git         NOT FOUND"
fi
say ""

if [ "$PY_OK" = 1 ] && [ "$GIT_OK" = 1 ]; then
    say "  Nothing to install. chamnan needs no packages beyond these — it is standard library only."
    exit 0
fi

if [ -z "$PKG_CMD" ]; then
    say "  Something is missing and no package manager was recognised on this system."
    say "  Install Python $MIN_MAJOR.$MIN_MINOR or newer and git by whatever means this machine uses."
    exit 1
fi

say "  Fix, using $PKG_NAME:"
say ""
say "      $PKG_CMD"
say ""
if [ "$WANT_INSTALL" = 1 ]; then
    say "  Running it now (--install was given)."
    say ""
    sh -c "$PKG_CMD" || { say ""; say "  That failed. Run it by hand and read what it says."; exit 1; }
    say ""
    say "  Done. Run this script again with no arguments to confirm."
    exit 0
fi
say "  Re-run with --install to have this script run that for you."
exit 1
