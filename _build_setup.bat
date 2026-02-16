@echo off
cd /d "%~dp0"

echo ============================================
echo   R-Converter - Crea Setup Installabile
echo ============================================
echo.
echo Cartella: %CD%
echo.

REM Verifica che esista la cartella dist/R-Converter (creata da clean_and_build)
if not exist "dist\R-Converter\R-Converter.exe" (
    echo ERRORE: dist\R-Converter\R-Converter.exe non trovata!
    echo.
    echo La cartella dist viene creata da _clean_and_build.bat
    echo Esegui _clean_and_build.bat e poi riprova _build_setup.bat
    echo.
    goto :fine
)

echo Cerco Inno Setup...
set ISCC=

REM Percorsi standard Inno Setup 6
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set ISCC=C:\Program Files\Inno Setup 6\ISCC.exe

REM Inno Setup 5
if exist "C:\Program Files (x86)\Inno Setup 5\ISCC.exe" set ISCC=C:\Program Files (x86)\Inno Setup 5\ISCC.exe
if exist "C:\Program Files\Inno Setup 5\ISCC.exe" set ISCC=C:\Program Files\Inno Setup 5\ISCC.exe

if defined ISCC (
    echo Trovato: %ISCC%
    echo.
    echo Compilazione setup in corso...
    "%ISCC%" installer.iss
    if %ERRORLEVEL% equ 0 (
        echo.
        echo [OK] Setup creato con successo!
        echo.
        echo File: installer_output\R-Converter_Setup_v1.3.1.exe
        echo.
        echo Copia questo file sul nuovo PC ed eseguilo per installare.
    ) else (
        echo [ERRORE] Compilazione fallita. Controlla i messaggi sopra.
    )
) else (
    echo.
    echo Inno Setup NON TROVATO.
    echo.
    echo Per creare il setup installabile:
    echo.
    echo 1. Scarica e installa Inno Setup (gratuito):
    echo    https://jrsoftware.org/isdl.php
    echo.
    echo 2. Dopo l'installazione, esegui di nuovo questo script
    echo    oppure:
    echo    - Apri Inno Setup Compiler
    echo    - File ^> Apri ^> installer.iss
    echo    - Compila (Ctrl+F9)
    echo    - Il setup sara' in: installer_output\R-Converter_Setup_v1.3.1.exe
    echo.
)

:fine
echo.
pause
