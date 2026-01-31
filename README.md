OCT – Software de Adquisición (Python)
================================

DESCRIPCIÓN
-----------
Este software permite la adquisición y procesamiento de datos OCT utilizando:

- Espectrómetro Ocean Insight HR4000
- Controlador de motores Newport ESP301
- Interfaz gráfica en PyQt5
- Procesamiento FFT / CZT en Python

El software es PORTABLE: no requiere instalación de Python ni dependencias adicionales.


ESTRUCTURA DEL PROYECTO
----------------------
OCT-Python-VL/
├─ run_OCT.bat              ← Ejecutar el software
├─ main.py
├─ oct_gui.py
├─ core_*.py
├─ venv/                    ← Entorno Python interno (NO tocar)
├─ python/                  ← Python embebido (NO tocar)
├─ drivers/                 ← Drivers de hardware
├─ Barridos Guardados/      ← Datos adquiridos
└─ README.txt


INSTALACIÓN EN UNA PC NUEVA (ORDEN OBLIGATORIO)
-----------------------------------------------

REQUISITOS
- Windows 10 / 11 (64-bit)
- Permisos de administrador
- Hardware DESCONECTADO al inicio


1) DRIVER NEWPORT ESP301
-----------------------
Ruta:
drivers\ESP301_USB_Driver\

Ejecutar COMO ADMINISTRADOR:
ESP301 Utility Installer Win64.exe

- NO ejecutar archivos dentro de 32-bit o 64-bit
- Esperar a que finalice la instalación

Conectar el ESP301 SOLO DESPUÉS de instalar el driver.


2) DRIVER / SDK OCEAN INSIGHT HR4000
-----------------------------------
Ruta:
drivers\OceanInsight\

Ejecutar COMO ADMINISTRADOR:
OmniDriver_2.7.3_win64.exe

- Usar opciones por defecto
- Requerido para el funcionamiento del espectrómetro vía seabreeze

Conectar el HR4000 DESPUÉS de la instalación.


3) REINICIAR LA PC
------------------
Este paso es OBLIGATORIO.


4) EJECUTAR EL SOFTWARE
----------------------
En la carpeta principal del proyecto:

Doble click en:
run_OCT.bat

- NO instalar Python
- NO ejecutar pip
- NO modificar archivos del proyecto

La interfaz gráfica debería abrirse automáticamente.


USO NORMAL
----------
- Los datos se guardan en:
  Barridos Guardados\
- Formato de guardado: .npz con metadata incluida
- El aborto de barridos es seguro y retorna a la posición inicial


REGLAS DEL LABORATORIO
---------------------
NO ejecutar pip install
NO actualizar librerías
NO modificar venv/ ni python/
NO ejecutar otros instaladores fuera de los indicados

Para pruebas o cambios:
- Copiar toda la carpeta
- Trabajar sobre la copia


RESOLUCIÓN DE PROBLEMAS BÁSICOS
-------------------------------
- El software no abre:
  Verificar drivers instalados y reinicio de la PC

- El ESP301 no responde:
  Verificar driver USB y puerto COM asignado

- El HR4000 no se detecta:
  Verificar OmniDriver y reconectar el dispositivo


VERSIÓN
-------
Paquete de software OCT congelado y reproducible.
No modificar sin validación previa.
