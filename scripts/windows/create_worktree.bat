@echo off
setlocal enabledelayedexpansion

REM ==============================================================================
REM Hannovators Deep Researcher - Worktree Setup Script
REM Usage:
REM   create_worktree.bat <branch-name> <slot 1-9> [full|backend|frontend|bare]
REM
REM Creates ..\hdr_wt_<slot> with its own .env, ports, SQLite database, .venv,
REM and node_modules. Ports follow the table in AGENTS.md:
REM   API_PORT  = 8001 + 10 * slot   (main repository uses 8001)
REM   VITE_PORT = 5174 + slot        (main repository uses 5174)
REM Run from the main repository root.
REM ==============================================================================

if "%~1"=="" goto :usage
if "%~2"=="" goto :usage

set "BRANCH=%~1"
set "SLOT=%~2"
set "MODE=full"

REM Validate slot (single digit 1-9)
set "SLOT_OK=0"
for %%N in (1 2 3 4 5 6 7 8 9) do if "%SLOT%"=="%%N" set "SLOT_OK=1"
if "%SLOT_OK%"=="0" (
    echo [ERROR] Slot must be a number from 1 to 9. Got '%SLOT%'.
    goto :usage
)

if /i "%~3"=="full" set "MODE=full"
if /i "%~3"=="fullstack" set "MODE=full"
if /i "%~3"=="backend" set "MODE=backend"
if /i "%~3"=="be" set "MODE=backend"
if /i "%~3"=="frontend" set "MODE=frontend"
if /i "%~3"=="fe" set "MODE=frontend"
if /i "%~3"=="ui" set "MODE=frontend"
if /i "%~3"=="bare" set "MODE=bare"
if /i "%~3"=="none" set "MODE=bare"

set /a API_PORT=8001 + 10 * %SLOT%
set /a VITE_PORT=5174 + %SLOT%
set "FOLDER=hdr_wt_%SLOT%"
set "TARGET_PATH=..\%FOLDER%"

if exist "%TARGET_PATH%" (
    echo [ERROR] '%TARGET_PATH%' already exists. Delete it first with:
    echo         scripts\windows\delete_worktree.bat %SLOT%
    exit /b 1
)

echo.
echo -------------------------------------------------------
echo Setting up worktree: %BRANCH%
echo Path:  %TARGET_PATH%
echo Mode:  [%MODE%]
echo Ports: API_PORT=%API_PORT%  VITE_PORT=%VITE_PORT%
echo -------------------------------------------------------

REM 1. Create Git worktree (local branch, then remote branch, else new branch from main)
git show-ref --verify --quiet refs/heads/%BRANCH%
if not errorlevel 1 (
    echo [1/5] Checking out existing local branch '%BRANCH%'...
    git worktree add "%TARGET_PATH%" "%BRANCH%"
) else (
    git show-ref --verify --quiet refs/remotes/origin/%BRANCH%
    if not errorlevel 1 (
        echo [1/5] Checking out remote branch 'origin/%BRANCH%'...
        git worktree add --track -b "%BRANCH%" "%TARGET_PATH%" "origin/%BRANCH%"
    ) else (
        echo [1/5] Creating new branch '%BRANCH%' from main...
        git worktree add -b "%BRANCH%" "%TARGET_PATH%" main
    )
)
if errorlevel 1 (
    echo [ERROR] Failed to create git worktree for '%BRANCH%'.
    exit /b 1
)

REM 2. Write .env: copy the main .env (or .env.example), drop DATABASE_URL and ports, set slot ports
if exist ".env" (
    echo [2/5] Copying root .env to '%TARGET_PATH%\.env'...
    copy /Y ".env" "%TARGET_PATH%\.env" >nul
) else (
    echo [2/5] [WARNING] No root .env found. Copying .env.example. Fill in API keys before live runs.
    copy /Y ".env.example" "%TARGET_PATH%\.env" >nul
)
powershell -NoProfile -Command ^
    "$p = Join-Path (Resolve-Path '%TARGET_PATH%') '.env'; " ^
    "$c = @(Get-Content -LiteralPath $p | Where-Object { $_ -notmatch '^\s*(API_PORT|VITE_PORT|DATABASE_URL)\s*=' }); " ^
    "$c += ''; $c += '# Worktree slot %SLOT% ports (written by create_worktree.bat)'; " ^
    "$c += 'API_PORT=%API_PORT%'; $c += 'VITE_PORT=%VITE_PORT%'; " ^
    "Set-Content -LiteralPath $p -Value $c -Encoding ASCII"
if errorlevel 1 (
    echo [ERROR] Failed to write ports into '%TARGET_PATH%\.env'.
    exit /b 1
)

REM 3. Backend setup (uv sync + migrations into the worktree's own data\hannovators.db)
if /i "%MODE%"=="frontend" (
    echo [3/5] [SKIP] Mode is 'frontend' - skipping backend setup.
) else if /i "%MODE%"=="bare" (
    echo [3/5] [SKIP] Mode is 'bare' - skipping backend setup.
) else (
    echo [3/5] Installing backend with 'uv sync --locked'...
    pushd "%TARGET_PATH%"
    call uv sync --locked
    if errorlevel 1 (
        echo [ERROR] 'uv sync --locked' failed in '%TARGET_PATH%'.
        popd
        exit /b 1
    )
    echo [3/5] Applying migrations with 'uv run alembic upgrade head'...
    call uv run alembic upgrade head
    if errorlevel 1 (
        echo [WARNING] Database migration reported an issue in '%TARGET_PATH%'.
    )
    popd
)

REM 4. Frontend setup (pnpm install)
if /i "%MODE%"=="backend" (
    echo [4/5] [SKIP] Mode is 'backend' - skipping frontend setup.
) else if /i "%MODE%"=="bare" (
    echo [4/5] [SKIP] Mode is 'bare' - skipping frontend setup.
) else (
    if exist "%TARGET_PATH%\frontend\package.json" (
        echo [4/5] Installing frontend with 'pnpm install --frozen-lockfile'...
        pushd "%TARGET_PATH%\frontend"
        call pnpm install --frozen-lockfile
        if errorlevel 1 (
            echo [ERROR] 'pnpm install' failed in '%TARGET_PATH%\frontend'.
            popd
            exit /b 1
        )
        popd
    ) else (
        echo [4/5] [INFO] No frontend directory on this branch. Skipping frontend setup.
    )
)

REM 5. CodeGraph initialization (optional)
where codegraph >nul 2>&1
if not errorlevel 1 (
    echo [5/5] Initializing CodeGraph index with 'codegraph init -y'...
    pushd "%TARGET_PATH%"
    call codegraph init -y
    popd
) else (
    echo [5/5] [SKIP] 'codegraph' CLI not found.
)

echo.
echo [OK] Worktree '%BRANCH%' ready at '%TARGET_PATH%' [%MODE%].
echo      API_PORT=%API_PORT%  VITE_PORT=%VITE_PORT%
exit /b 0

:usage
echo.
echo Usage:
echo   create_worktree.bat ^<branch-name^> ^<slot 1-9^> [mode]
echo.
echo Modes:
echo   full (default)    - Backend (uv sync + migrations) and frontend (pnpm install)
echo   backend (be)      - Backend only
echo   frontend (fe, ui) - Frontend only
echo   bare (none)       - Git checkout and .env only
echo.
echo Ports per slot: API_PORT = 8001 + 10 * slot, VITE_PORT = 5174 + slot (see AGENTS.md).
echo.
echo Examples:
echo   create_worktree.bat phase0/backend 1
echo   create_worktree.bat lane/a3-websearch 3 backend
exit /b 1
