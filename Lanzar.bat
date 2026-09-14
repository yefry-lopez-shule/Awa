@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo   Awa
echo ============================================
echo.

if not exist ".venv\Scripts\python.exe" (
    call :fail "No se encontro el entorno virtual en .venv\. Este lanzador espera un entorno ya configurado."
)

rem gettext (xgettext/msgfmt) viene de conda-forge, no del gettext de
rem 'defaults' que trae Windows por defecto en el PATH del sistema.
rem Ver AGENTS.md.
set "PATH=C:\Users\jeff0\anaconda3\Library\bin;%PATH%"

echo Compilando catalogos de idioma (es/en)...
".venv\Scripts\python.exe" manage.py compilemessages --ignore=.venv
if errorlevel 1 call :fail "No se pudieron compilar los catalogos de idioma. Revisa el mensaje de arriba."

echo.
echo Aplicando migraciones pendientes...
".venv\Scripts\python.exe" manage.py migrate
if errorlevel 1 call :fail "No se pudieron aplicar las migraciones. Revisa el mensaje de arriba."

echo.
echo Iniciando el servidor. El navegador se abre apenas responda...
echo Para detener Awa, cerra esta ventana.
echo.

rem Sondea (fuera de este proceso, sin bloquear el servidor) hasta que
rem realmente conteste antes de abrir el navegador, en vez de adivinar un
rem tiempo fijo — hasta 20s, en pasos de medio segundo.
start "" /min powershell -NoProfile -WindowStyle Hidden -Command "for($i=0;$i -lt 40;$i++){try{Invoke-WebRequest -Uri 'http://127.0.0.1:8000/' -UseBasicParsing -TimeoutSec 1 | Out-Null; break}catch{Start-Sleep -Milliseconds 500}}; Start-Process 'http://127.0.0.1:8000/'"

".venv\Scripts\python.exe" manage.py runserver 8000
if errorlevel 1 call :fail "El servidor no pudo iniciar (revisa si el puerto 8000 ya esta en uso)."

echo.
echo El servidor se detuvo.
pause
exit /b 0

:fail
echo.
echo %~1
echo.
pause
exit /b 1
