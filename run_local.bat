@echo off
echo ============================================
echo  BVC Trading Dashboard - Lancement local
echo ============================================

REM Charge les variables depuis .env si present
if exist .env (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        if not "%%A"=="" if not "%%A:~0,1%"=="#" set "%%A=%%B"
    )
    echo Variables .env chargees.
) else (
    echo ATTENTION: .env introuvable. Lancez setup_local.bat d abord.
)

echo.
echo Demarrage Flask sur http://localhost:5000
echo Ctrl+C pour arreter.
echo.
python app.py
pause
