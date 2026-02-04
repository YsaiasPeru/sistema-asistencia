@echo off
:menu
cls
echo =========================
echo   SISTEMA ASISTENCIA
echo =========================
echo 1. Instalar dependencias
echo 2. Ejecutar sistema
echo 3. Salir
echo.

set /p op=Seleccione opcion:

if %op%==1 pip install -r requirements.txt
if %op%==2 python app.py
if %op%==3 exit

pause
goto menu
