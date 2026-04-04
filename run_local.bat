@echo off
echo ============================================
echo  BVC Trading Dashboard - Lancement local
echo ============================================
echo.
echo Demarrage Flask sur http://localhost:5000
echo (Le fichier .env est charge automatiquement)
echo Ctrl+C pour arreter.
echo.
cd /d "%~dp0"
python app.py
pause
