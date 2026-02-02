# OCT – Software de Adquisición (Python)

## DESCRIPCIÓN

Este software permite la adquisición y procesamiento de datos OCT utilizando:

- Espectrómetro Ocean Insight HR4000
- Controlador de motores Newport ESP301
- Interfaz gráfica en PyQt5
- Procesamiento FFT / CZT en Python

El software es PORTABLE: no requiere instalación de Python ni dependencias adicionales.

## ESTRUCTURA DEL PROYECTO

```
OCT-Python-VL/
├─ run*OCT.bat ← Ejecutar el software
├─ main.py
├─ oct_gui.py
├─ core*\*.py
├─ venv/ ← Entorno Python interno (NO tocar)
├─ python/ ← Python embebido (NO tocar)
├─ drivers/ ← Drivers de hardware
├─ Barridos Guardados/ ← Datos adquiridos
└─ README.txt
```

## INSTALACIÓN EN UNA PC NUEVA (ORDEN OBLIGATORIO)

### REQUISITOS

- Windows 10 / 11 (64-bit)
- Permisos de administrador
- Hardware DESCONECTADO al inicio

#### 1. DRIVER NEWPORT ESP301

Ruta: `drivers\ESP301_USB_Driver\`.

1. Ejecutar COMO ADMINISTRADOR: `ESP301 Utility Installer Win64.exe`.

- NO ejecutar archivos dentro de 32-bit o 64-bit.
- Esperar a que finalice la instalación.

2. Conectar el ESP301 SOLO DESPUÉS de instalar el driver.

#### 2. DRIVER / SDK OCEAN INSIGHT HR4000

Ruta: `drivers\OceanInsight\`.

1. Ejecutar COMO ADMINISTRADOR: `OmniDriver_2.7.3_win64.exe`.

- Usar opciones por defecto
- Requerido para el funcionamiento del espectrómetro vía seabreeze

2. Conectar el HR4000 DESPUÉS de la instalación.

#### 3. REINICIAR LA PC

Este paso es OBLIGATORIO.

#### 4. EJECUTAR EL SOFTWARE

En la carpeta principal del proyecto:

Doble click en: `run_OCT.bat`.

- NO instalar Python.
- NO ejecutar pip.
- NO modificar archivos del proyecto.

La interfaz gráfica debería abrirse automáticamente.

## USO NORMAL

- Los datos se guardan en: `Barridos Guardados\`.
- Formato de guardado: `.npz` con metadata incluida.
- El aborto de barridos es seguro y retorna a la posición inicial.

## REGLAS DEL LABORATORIO

- NO ejecutar `pip install`.
- NO actualizar librerías.
- NO modificar `venv/` ni `python/`.
- NO ejecutar otros instaladores fuera de los indicados.

Para pruebas o cambios:

- Copiar toda la carpeta
- Trabajar sobre la copia

## RESOLUCIÓN DE PROBLEMAS BÁSICOS

- El software no abre:

  Verificar drivers instalados y reinicio de la PC

- El ESP301 no responde:

  Verificar driver USB y puerto COM asignado

- El HR4000 no se detecta:

  Verificar OmniDriver y reconectar el dispositivo

## VERSIÓN

Paquete de software OCT congelado y reproducible.
No modificar sin validación previa.

## GUÍA DE EDICIÓN DEL CÓDIGO

La aplicación usa la versión de Python 3.10.x por motivos de compatibilidad con el hardware.

### Programación en Windows

Para programar en Windows, se recomienda descargar un instalador para Windows de Python 3.10.8 desde https://www.python.org/downloads/windows/. Durante la instalación, habilitar la opción de instalar el `py launcher` (viene habilitada por defecto). Hecho esto, puede configurar el entorno de programación siguiendo los siguientes pasos:

1. Abrir una terminal (CMD o PowerShell) en la carpeta `PY310-OCT-VL\`.
2. Crear un entorno virtual con la versión de Python indicada:

   ```
   py -3.10 -m venv venv
   ```

3. Habilitar el entorno virtual:

   ```
   venv\Scripts\activate
   ```

4. Instalar las dependencias:

   ```
   pip install -r requirements.txt
   ```

Puede probar la aplicación con

```
python main.py
```

Si instala librerías con `pip install <nombre>`, actualizar el archivo de dependencias con

```
pip freeze > requirementx.txt
```

Para volver a compilar la aplicación con los cambios realizados, instalar PyInstaller con `pip install pyinstaller`. Luego ejecutar el siguiente comando:

```
pyinstaller main.py --onefile --noconsole --name Run
```
