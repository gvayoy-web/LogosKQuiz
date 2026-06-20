@echo off
echo ================================================
echo   COMPETENCIA BIBLICA - Instalando dependencias
echo ================================================
pip install flask flask-cors waitress

echo.
echo ================================================
echo   Iniciando servidor (Waitress - Produccion)
echo   Panel:   http://localhost:5000/control
echo   Display: http://localhost:5000/display
echo ================================================
python app.py
pause
