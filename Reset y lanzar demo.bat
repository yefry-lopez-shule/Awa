@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo   Awa - Reset y lanzar demo
echo ============================================
echo.
echo Esto va a:
echo   1. Respaldar db.sqlite3 tal como esta ahora
echo   2. BORRAR todo el progreso real (Cursos, Terminos, notas, registros de
echo      estudio, bloques de disponibilidad), dejando el plan de estudios
echo      (Plan/Bloques/Cursos/prerequisitos) intacto
echo   3. Lanzar Awa desde una casilla de verificacion de inicio en blanco,
echo      lista para una demo
echo.

if not exist ".venv\Scripts\python.exe" (
    call :fail "No se encontro el entorno virtual en .venv\. Este lanzador espera un entorno ya configurado."
)

if not exist "db.sqlite3" (
    call :fail "No se encontro db.sqlite3. Corre Lanzar.bat primero para crear la base de datos."
)

set /p CONFIRM="Escribi 'si' para continuar, cualquier otra cosa cancela: "
if /i not "%CONFIRM%"=="si" (
    echo.
    echo Cancelado. No se cambio nada.
    echo.
    pause
    exit /b 0
)

rem gettext (xgettext/msgfmt) viene de conda-forge, no del gettext de
rem 'defaults' que trae Windows por defecto en el PATH del sistema.
rem Ver AGENTS.md.
set "PATH=C:\Users\jeff0\anaconda3\Library\bin;%PATH%"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "TIMESTAMP=%%i"

echo.
echo Respaldando db.sqlite3...
copy /y "db.sqlite3" "db.sqlite3.bak-%TIMESTAMP%" >nul
if errorlevel 1 call :fail "No se pudo respaldar db.sqlite3."
echo Respaldo guardado como db.sqlite3.bak-%TIMESTAMP%

echo.
echo Borrando progreso...
".venv\Scripts\python.exe" manage.py reset_demo_progress
if errorlevel 1 call :fail "No se pudo borrar el progreso. Revisa el mensaje de arriba. El respaldo db.sqlite3.bak-%TIMESTAMP% quedo intacto."

echo.
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
