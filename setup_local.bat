@echo off
echo ============================================
echo  BVC Trading Dashboard - Setup local
echo ============================================

REM Installe les dependances Python
echo.
echo [1/3] Installation des dependances...
pip install flask==3.0.3 anthropic==0.40.0 gunicorn==23.0.0 requests==2.32.3 python-dotenv
if %errorlevel% neq 0 (
    echo ERREUR: pip install a echoue. Verifiez que Python est installe.
    pause
    exit /b 1
)

REM Cree le fichier .env s'il n'existe pas
if not exist .env (
    echo.
    echo [2/3] Creation du fichier .env...
    (
        echo ANTHROPIC_API_KEY=sk-ant-xxxxxx
        echo DRAHMI_API_KEY=drahmi_live_xxxxxx
    ) > .env
    echo Fichier .env cree. EDITEZ-LE avec vos vraies cles avant de lancer.
) else (
    echo [2/3] Fichier .env existant conserve.
)

echo.
echo [3/3] Setup termine.
echo.
echo ============================================
echo  Pour lancer l'application :
echo    run_local.bat
echo  Puis ouvrez : http://localhost:5000
echo ============================================
pause
