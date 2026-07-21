@echo off
:: Standalone Windows builder using PyInstaller
title Creador de ejecutable Windows - Yt-Dlp GUI
echo ======================================================
echo Creando Ejecutable Standalone para Windows (PyInstaller)
echo ======================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] No se ha encontrado Python en el sistema.
    echo Por favor, instala Python 3 e intenta de nuevo.
    echo Descargalo desde: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo [1/3] Instalando dependencias necesarias...
python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt

echo.
echo [2/3] Compilando aplicacion con PyInstaller...
python -m PyInstaller --clean yt-dlp-gui.spec

echo.
if %errorlevel% eq 0 (
    echo [3/3] ¡Compilacion completada con exito!
    echo El archivo ejecutable se encuentra en: dist\yt-dlp-gui.exe
    echo.
    echo NOTA: La primera vez que abras el programa en Windows podria tardar
    echo unos segundos en descomprimir el entorno Python autocontenido.
) else (
    echo [ERROR] Ocurrio un error durante la compilacion. Revisa el log superior.
)
echo.
pause
