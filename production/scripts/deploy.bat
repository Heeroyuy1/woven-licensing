@echo off
title Woven Model Licensing Server — Deployment
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ── Colors using ANSI escape codes ──────────────────────────
set "ESC="
for /f "delims=#" %%a in ('"prompt #$E# & for %%b in (1) do rem"') do set "ESC=%%a"
set "BOLD=%ESC%[1m"
set "DIM=%ESC%[2m"
set "RED=%ESC%[91m"
set "GREEN=%ESC%[92m"
set "YELLOW=%ESC%[93m"
set "CYAN=%ESC%[96m"
set "WHITE=%ESC%[97m"
set "RESET=%ESC%[0m"

:: ── Banner ─────────────────────────────────────────────────
echo.
echo %BOLD%%CYAN%================================================================%RESET%
echo %BOLD%%WHITE%  Woven Model — Licensing Server Deployment%RESET%
echo %BOLD%%CYAN%================================================================%RESET%
echo.
echo %DIM%  This script deploys the Woven Model Licensing Server%RESET%
echo %DIM%  using Docker Compose.%RESET%
echo.

:: ── Helper: print with color ─────────────────────────────────
call :set_bg "%~1"
goto :eof

:: ── Step 1: Check Docker ─────────────────────────────────────
echo %BOLD%[1/6] Checking prerequisites...%RESET%

where docker >nul 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo %RED%  Docker not found!%RESET%
    echo.
    echo %YELLOW%  Please install Docker Desktop:%RESET%
    echo    https://docs.docker.com/desktop/install/windows-install/
    echo.
    echo %YELLOW%  After installation, restart this script.%RESET%
    echo.
    pause
    exit /b 1
)
echo %GREEN%  [OK] Docker found%RESET%

where docker-compose >nul 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo %YELLOW%  [WARN] docker-compose not found, trying docker compose...%RESET%
    docker compose version >nul 2>nul
    if !ERRORLEVEL! NEQ 0 (
        echo %RED%  Neither docker-compose nor docker compose found!%RESET%
        echo.
        echo %YELLOW%  Please ensure Docker Compose is installed:%RESET%
        echo    https://docs.docker.com/compose/install/
        echo.
        pause
        exit /b 1
    )
    set "COMPOSE_CMD=docker compose"
) else (
    set "COMPOSE_CMD=docker-compose"
)
echo %GREEN%  [OK] Docker Compose available%RESET%

echo.

:: ── Step 2: Check .env.production ─────────────────────────────
echo %BOLD%[2/6] Checking environment configuration...%RESET%

if not exist "..\.env.production" (
    if exist "..\.env.production.example" (
        echo %YELLOW%  .env.production not found, copying from example...%RESET%
        copy "..\.env.production.example" "..\.env.production" >nul
        if !ERRORLEVEL! EQU 0 (
            echo %GREEN%  [OK] Copied .env.production.example to .env.production%RESET%
        ) else (
            echo %RED%  [FAIL] Could not copy .env.production.example%RESET%
        )
    ) else (
        echo %RED%  .env.production not found and no example template exists!%RESET%
        echo %YELLOW%  Create .env.production first:%RESET%
        echo    Copy ..\licensing-server\.env.example to ..\.env.production
        echo    Edit with your settings.
        pause
        exit /b 1
    )
) else (
    echo %GREEN%  [OK] .env.production found%RESET%
)

echo.

:: ── Step 3: Check Signing Keys ───────────────────────────────
echo %BOLD%[3/6] Checking signing keys...%RESET%

:: Check if SIGNING keys are set in .env
findstr /B /I "SIGNING_PRIVATE_KEY" "..\.env.production" >nul 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo %YELLOW%  Signing keys not configured. Running key generator...%RESET%
    if exist "generate_keys.py" (
        python generate_keys.py
        if !ERRORLEVEL! EQU 0 (
            echo %GREEN%  [OK] Signing keys generated%RESET%
        ) else (
            echo %RED%  [FAIL] Key generation failed%RESET%
            pause
            exit /b 1
        )
    ) else (
        echo %RED%  generate_keys.py not found in current directory!%RESET%
        echo %YELLOW%  Please run the key generator manually:%RESET%
        echo    python %~dp0..\..\licensing-server\backend\scripts\generate_keys.py
        pause
        exit /b 1
    )
) else (
    echo %GREEN%  [OK] Signing keys configured%RESET%
)

echo.

:: ── Step 4: Domain Name ─────────────────────────────────────
echo %BOLD%[4/6] Domain configuration...%RESET%
set /p DOMAIN_NAME=%BOLD%  Enter domain name for SSL (or leave blank for localhost): %RESET%

if not "!DOMAIN_NAME!"=="" (
    echo %GREEN%  [OK] Domain set to: !DOMAIN_NAME!%RESET%
    :: Update .env.production with domain
    findstr /B /I "DOMAIN" "..\.env.production" >nul 2>nul
    if !ERRORLEVEL! EQU 0 (
        :: Replace existing DOMAIN line
        powershell -Command "(Get-Content '..\.env.production') -replace '(?i)^DOMAIN=.*','DOMAIN=!DOMAIN_NAME!' | Set-Content '..\.env.production'"
    ) else (
        echo DOMAIN=!DOMAIN_NAME!>> "..\.env.production"
    )
) else (
    echo %YELLOW%  Using localhost (no SSL)%RESET%
)

echo.

:: ── Step 5: Start Services ───────────────────────────────────
echo %BOLD%[5/6] Starting services with Docker Compose...%RESET%
echo %DIM%  Running: !COMPOSE_CMD! up -d%RESET%

if exist "..\docker-compose.yml" (
    pushd ..
    !COMPOSE_CMD! up -d
    set "EXIT_CODE=!ERRORLEVEL!"
    popd

    if !EXIT_CODE! EQU 0 (
        echo %GREEN%  [OK] Services started successfully%RESET%
    ) else (
        echo %RED%  [FAIL] Docker Compose failed with code !EXIT_CODE!%RESET%
        echo %YELLOW%  Check logs with: !COMPOSE_CMD! logs%RESET%
        pause
        exit /b !EXIT_CODE!
    )
) else (
    echo %RED%  docker-compose.yml not found in parent directory!%RESET%
    echo %YELLOW%  Expected at: ..\docker-compose.yml%RESET%
    pause
    exit /b 1
)

echo.

:: ── Step 6: Success ─────────────────────────────────────────
echo %BOLD%%GREEN%================================================================%RESET%
echo %BOLD%%WHITE%  Deployment Complete!%RESET%
echo %BOLD%%GREEN%================================================================%RESET%
echo.
echo %BOLD%  Woven Model Licensing Server%RESET%
echo.
if not "!DOMAIN_NAME!"=="" (
    echo    API:        %CYAN%https://!DOMAIN_NAME!%RESET%
    echo    Admin UI:   %CYAN%https://!DOMAIN_NAME!/admin%RESET%
) else (
    echo    API:        %CYAN%http://localhost:8000%RESET%
    echo    Admin UI:   %CYAN%http://localhost:8000/admin%RESET%
)
echo.
echo %BOLD%  Next steps:%RESET%
echo.
echo    %DIM%1.%RESET% Seed admin user:  %CYAN%python seed_admin.py --seed-products%RESET%
echo    %DIM%2.%RESET% Generate licenses: %CYAN%python license_cli.py generate --product STRATUM --user 1 --type perpetual%RESET%
echo    %DIM%3.%RESET% View logs:         %CYAN%!COMPOSE_CMD! logs -f%RESET%
echo    %DIM%4.%RESET% Stop services:     %CYAN%!COMPOSE_CMD! down%RESET%
echo.
echo %DIM%  Support: jude@wovenmodel.com%RESET%
echo.
echo %BOLD%%GREEN%================================================================%RESET%
echo.

:: Pause only if running interactively
echo Press any key to exit...
pause >nul 2>nul

exit /b 0