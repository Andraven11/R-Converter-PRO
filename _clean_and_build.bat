@echo off
echo ============================================
echo   R-Converter PRO v2.0.0 - Clean + Build
echo ============================================
echo.

REM Check Python
python --version
if %ERRORLEVEL% neq 0 (
    echo ERRORE: Python non trovato!
    echo Assicurati che Python sia nel PATH
    pause
    exit /b 1
)

REM Check PyInstaller (usa python -m perche' pyinstaller potrebbe non essere nel PATH)
python -m PyInstaller --version
if %ERRORLEVEL% neq 0 (
    echo PyInstaller non trovato, installo...
    pip install pyinstaller
)

echo.
echo --- Download FFmpeg (per bundle) ---
python _download_ffmpeg_build.py
if %ERRORLEVEL% neq 0 (
    echo [AVVISO] Download FFmpeg fallito. Build senza FFmpeg bundled.
) else (
    echo [OK] FFmpeg pronto per la build
)
echo.
echo --- Pulizia vecchie build ---
if exist "dist" (
    rmdir /s /q dist
    echo [OK] Cartella dist rimossa
)
if exist "build" (
    rmdir /s /q build
    echo [OK] Cartella build rimossa
)
echo.

echo ============================================
echo   1/2 - Build INSTALLER (cartella per Inno Setup)
echo ============================================
echo.

python -m PyInstaller R-Converter.spec --noconfirm --clean

if %ERRORLEVEL% equ 0 (
    echo.
    echo [OK] Versione Installer pronta
) else (
    echo [ERRORE] Build Installer fallita!
    pause
    exit /b 1
)

echo.
echo ============================================
echo   2/2 - Build PORTABLE (singolo .exe)
echo ============================================
echo.

python -m PyInstaller R-Converter_Portable.spec --noconfirm --clean

if %ERRORLEVEL% equ 0 (
    echo.
    echo [OK] Versione Portable pronta
) else (
    echo [ERRORE] Build Portable fallita!
    pause
    exit /b 1
)

echo.
echo ============================================
echo   3/3 - Build SETUP (Inno Setup)
echo ============================================
echo.

set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set ISCC=C:\Program Files\Inno Setup 6\ISCC.exe

if defined ISCC (
    "%ISCC%" installer.iss
    if %ERRORLEVEL% equ 0 (
        echo [OK] Setup creato in installer_output\R-Converter_PRO_Setup_v2.0.0.exe
    ) else (
        echo [ERRORE] Compilazione Inno Setup fallita
    )
) else (
    echo Inno Setup non trovato. Compila manualmente:
    echo   1. Apri installer.iss con Inno Setup Compiler
    echo   2. Compila (Ctrl+F9)
)

echo.
echo ============================================
echo   BUILD COMPLETATA!
echo ============================================
echo.
echo Versione Portable (singolo .exe):
if exist "dist\R-Converter_Portable.exe" (
    for %%F in ("dist\R-Converter_Portable.exe") do echo    dist\R-Converter_Portable.exe  [%%~zF bytes]
    echo    Pronto! Copia il file dove vuoi e lancia con doppio click.
) else (
    echo    [NON TROVATA]
)
echo.
echo Setup installabile (per altro PC):
if exist "installer_output\R-Converter_PRO_Setup_v2.0.0.exe" (
    for %%F in ("installer_output\R-Converter_PRO_Setup_v2.0.0.exe") do echo    installer_output\R-Converter_PRO_Setup_v2.0.0.exe  [%%~zF bytes]
    echo    Esegui su altro PC per installazione completa.
) else (
    echo    installer_output\R-Converter_PRO_Setup_v2.0.0.exe  [compila con Inno Setup]
)
echo.
pause
