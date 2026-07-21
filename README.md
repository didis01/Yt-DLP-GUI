# Yt-DLP GUI

Una interfaz gráfica moderna para **yt-dlp**, desarrollada en **Python** con **Tkinter**, que facilita la descarga de vídeo y audio desde plataformas compatibles mediante una experiencia de usuario intuitiva, sin necesidad de utilizar la línea de comandos.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)]()
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-4CAF50)]()
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Powered by yt-dlp](https://img.shields.io/badge/Powered%20by-yt--dlp-FF0000)](https://github.com/yt-dlp/yt-dlp)

---

## Características

- Interfaz gráfica moderna con tema oscuro.
- Análisis previo del contenido.
- Vista previa mediante miniatura.
- Información del vídeo (título, autor y duración).
- Descarga de vídeo y audio en múltiples formatos.
- Extracción de audio.
- Descarga e incrustación de subtítulos.
- Incrustación de metadatos y miniaturas.
- Monitorización del progreso en tiempo real.
- Consola integrada con la salida de **yt-dlp**.
- Cancelación de descargas.
- Actualización automática del ejecutable de **yt-dlp**.

---

## Capturas

| Pantalla principal |
|--------------------|
| ![](docs/main.png) |

---

## Formatos disponibles

### Vídeo

- Mejor calidad disponible
- MP4 hasta 1080p
- MP4 hasta 720p
- MP4 hasta 480p

### Audio

- MP3
- M4A
- WAV

---

## Compatibilidad

| Sistema operativo | Estado |
|-------------------|--------|
| Windows | ✅ Compatible |
| Linux | ✅ Compatible |

---

## Dependencias

### Requisitos del sistema

- Python 3.10 o superior
- FFmpeg

### Dependencias de Python

Todas las dependencias necesarias pueden instalarse mediante el archivo `requirements.txt`.

---

## Instalación

Clonar el repositorio:

```bash
git clone https://github.com/didis01/Yt-DLP-GUI.git

cd Yt-DLP-GUI
```

Instalar las dependencias:

```bash
pip install -r requirements.txt
```

Instalar **FFmpeg** y asegurarse de que se encuentra disponible en el `PATH` del sistema.

---

## Ejecución

### Linux

```bash
./run.sh
```

o

```bash
python3 yt_downloader.py
```

### Windows

```powershell
python yt_downloader.py
```

---

## Compilación

### Linux

```bash
chmod +x build.sh
./build.sh
```

### Windows

```bat
build.bat
```

Los scripts de compilación generan un ejecutable independiente utilizando **PyInstaller**.

---

## Tecnologías utilizadas

- Python
- Tkinter
- yt-dlp
- FFmpeg
- Pillow
- Requests
- PyInstaller

---

## Flujo de uso

1. Introducir la URL del contenido.
2. Analizar el enlace.
3. Revisar la información obtenida.
4. Seleccionar el formato de descarga.
5. Elegir la carpeta de destino.
6. Iniciar la descarga.
7. Supervisar el progreso en tiempo real.

---

## Aviso legal

**Yt-DLP GUI** es únicamente una interfaz gráfica para la herramienta **yt-dlp**.

El usuario es el único responsable del uso del software y debe respetar la legislación aplicable, los derechos de autor y los términos de servicio de las plataformas desde las que descargue contenido.

---

## Licencia

Este proyecto está distribuido bajo la **Apache License 2.0**.

Consulte el archivo [LICENSE](LICENSE) para obtener el texto completo de la licencia.

Copyright © 2026 Diego Martínez-Blay Díaz.

---

## Agradecimientos

Este proyecto se apoya en el excelente trabajo realizado por:

- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- FFmpeg
- La comunidad de Python
