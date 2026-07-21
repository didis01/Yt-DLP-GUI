#!/bin/bash
# Standalone Linux builder using PyInstaller

echo "======================================================"
echo "Creando Ejecutable Standalone para Linux (PyInstaller)"
echo "======================================================"
echo

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] No se ha encontrado Python 3 en el sistema."
    exit 1
fi

# Limpiar compilaciones anteriores
echo "[0/3] Limpiando compilaciones anteriores..."
rm -rf dist

echo
echo "[1/3] Instalando dependencias necesarias..."
pip install --user -r requirements-build.txt 2>/dev/null || \
pip install --user --break-system-packages -r requirements-build.txt

echo
echo "[2/3] Compilando aplicación con PyInstaller..."
python3 -m PyInstaller --clean yt-dlp-gui.spec

if [ $? -eq 0 ]; then
    # Eliminar archivos temporales de PyInstaller
    rm -rf build

    echo
    echo "[3/3] ¡Compilación completada con éxito!"
    echo "El archivo ejecutable se encuentra en: dist/yt-dlp-gui"
else
    echo
    echo "[ERROR] Ocurrió un error durante la compilación."
    exit 1
fi
