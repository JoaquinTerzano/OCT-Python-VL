# -*- coding: utf-8 -*-
"""
OCT GUI COMPLETO v1.0.0
Fecha: Enero 2026

Integra:
- Barrido 3D completo (X, Y, Z)
- Botón ABORTAR funcional
- Guardado formato v1.0.0 estandarizado
- Guardados parciales opcionales cada 10%
- Optimizaciones A1 + A2

@author: Lucas
"""

import numpy as np
from datetime import datetime
from scipy.signal import find_peaks
from scipy.interpolate import interp1d
import os

from PyQt5.QtWidgets import (
    QWidget, QMainWindow, QPushButton, QLabel, QDoubleSpinBox, QCheckBox,
    QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QMessageBox,
    QScrollArea  # Para scroll en panel izquierdo
)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt
import pyqtgraph as pg

from core_spectrometer import HRSpectrometer
from core_motors import ESP301, MotorError
from core_fft import detect_peaks_in_window, calculate_resolution, czt_zoom
from oct_data_saver import OCTDataSaver, generate_filename  # NUEVO: Formato v1.0.0


# ================= CONFIG =================
MAX_WINDOWS = 5
PEAKS_PER_WINDOW = 3
# =========================================


# ============================================================
# Worker de barrido
# ============================================================
class ScanWorker(QThread):
    point_acquired = pyqtSignal(float, float, float)  # MODIFICADO: Ahora emite (x, y, z)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)
    aborted = pyqtSignal()  # NUEVO: Señal para abortar

    def __init__(self, mot,
                 use_x, use_y, use_z,  # NUEVO: use_z
                 xin, xend, xstep,
                 yin, yend, ystep,
                 zin, zend, zstep,  # NUEVO: parámetros Z
                 settling_time=0.05):
        super().__init__()
        self.mot = mot
        self.use_x = use_x
        self.use_y = use_y
        self.use_z = use_z  # NUEVO
        self.xin = xin
        self.xend = xend
        self.xstep = abs(xstep)
        self.yin = yin
        self.yend = yend
        self.ystep = abs(ystep)
        self.zin = zin  # NUEVO
        self.zend = zend  # NUEVO
        self.zstep = abs(zstep)  # NUEVO
        self.settling_time = settling_time
        self._abort_flag = False  # NUEVO: Flag para abortar

    def abort(self):
        """Solicitar abortar el barrido de forma segura"""
        self._abort_flag = True
        print("⚠️  Abort solicitado - terminando punto actual...")

    def frange(self, a, b, s):
        """Generador de rango flotante"""
        if a == b:
            yield a
            return
        if b > a:
            v = a
            while v <= b + 1e-12:
                yield v
                v += s
        else:
            v = a
            while v >= b - 1e-12:
                yield v
                v -= s

    def run(self):
        """
        Ejecutar barrido con settling time y manejo robusto de errores.
        
        Estructura de barrido 3D:
        Para cada Z:
            Para cada Y:
                Para cada X:
                    Adquirir punto (x, y, z)
        """
        import time
        from core_motors import MotorError
        
        try:

            # ════════════════════════════════════════════════════════
            # BARRIDOS 1D
            # ════════════════════════════════════════════════════════
            if self.use_x and not self.use_y and not self.use_z:
                # Solo X
                for x in self.frange(self.xin, self.xend, self.xstep):
                    if self._abort_flag:  # NUEVO: Verificar abort
                        break
                    self.mot.goto_and_wait(1, x)
                    time.sleep(self.settling_time)
                    self.point_acquired.emit(x, 0.0, 0.0)

            elif self.use_y and not self.use_x and not self.use_z:
                # Solo Y
                for y in self.frange(self.yin, self.yend, self.ystep):
                    if self._abort_flag:  # NUEVO: Verificar abort
                        break
                    self.mot.goto_and_wait(2, y)
                    time.sleep(self.settling_time)
                    self.point_acquired.emit(0.0, y, 0.0)
                    
            elif self.use_z and not self.use_x and not self.use_y:
                # Solo Z (NUEVO)
                for z in self.frange(self.zin, self.zend, self.zstep):
                    if self._abort_flag:  # NUEVO: Verificar abort
                        break
                    self.mot.goto_and_wait(3, z)
                    time.sleep(self.settling_time)
                    self.point_acquired.emit(0.0, 0.0, z)

            # ════════════════════════════════════════════════════════
            # BARRIDOS 2D
            # ════════════════════════════════════════════════════════
            elif self.use_x and self.use_y and not self.use_z:
                # Barrido 2D: X-Y
                for y in self.frange(self.yin, self.yend, self.ystep):
                    if self._abort_flag:  # NUEVO: Verificar abort
                        break
                    self.mot.goto_and_wait(2, y)
                    time.sleep(self.settling_time)
                    
                    for x in self.frange(self.xin, self.xend, self.xstep):
                        if self._abort_flag:  # NUEVO: Verificar abort
                            break
                        self.mot.goto_and_wait(1, x)
                        time.sleep(self.settling_time)
                        self.point_acquired.emit(x, y, 0.0)
                        
            elif self.use_x and self.use_z and not self.use_y:
                # Barrido 2D: X-Z (NUEVO)
                for z in self.frange(self.zin, self.zend, self.zstep):
                    if self._abort_flag:  # NUEVO: Verificar abort
                        break
                    self.mot.goto_and_wait(3, z)
                    time.sleep(self.settling_time)
                    
                    for x in self.frange(self.xin, self.xend, self.xstep):
                        if self._abort_flag:  # NUEVO: Verificar abort
                            break
                        self.mot.goto_and_wait(1, x)
                        time.sleep(self.settling_time)
                        self.point_acquired.emit(x, 0.0, z)
                        
            elif self.use_y and self.use_z and not self.use_x:
                # Barrido 2D: Y-Z (NUEVO)
                for z in self.frange(self.zin, self.zend, self.zstep):
                    if self._abort_flag:  # NUEVO: Verificar abort
                        break
                    self.mot.goto_and_wait(3, z)
                    time.sleep(self.settling_time)
                    
                    for y in self.frange(self.yin, self.yend, self.ystep):
                        if self._abort_flag:  # NUEVO: Verificar abort
                            break
                        self.mot.goto_and_wait(2, y)
                        time.sleep(self.settling_time)
                        self.point_acquired.emit(0.0, y, z)

            # ════════════════════════════════════════════════════════
            # BARRIDO 3D (NUEVO)
            # ════════════════════════════════════════════════════════
            elif self.use_x and self.use_y and self.use_z:
                # Barrido 3D: Z → Y → X
                print(f"Iniciando barrido 3D:")
                print(f"  Z: {self.zin} → {self.zend} (step {self.zstep})")
                print(f"  Y: {self.yin} → {self.yend} (step {self.ystep})")
                print(f"  X: {self.xin} → {self.xend} (step {self.xstep})")
                
                for z in self.frange(self.zin, self.zend, self.zstep):
                    if self._abort_flag:  # NUEVO: Verificar abort
                        break
                    self.mot.goto_and_wait(3, z)
                    time.sleep(self.settling_time)
                    print(f"  Nivel Z={z:.3f} mm")
                    
                    for y in self.frange(self.yin, self.yend, self.ystep):
                        if self._abort_flag:  # NUEVO: Verificar abort
                            break
                        self.mot.goto_and_wait(2, y)
                        time.sleep(self.settling_time)
                        
                        for x in self.frange(self.xin, self.xend, self.xstep):
                            if self._abort_flag:  # NUEVO: Verificar abort
                                break
                            self.mot.goto_and_wait(1, x)
                            time.sleep(self.settling_time)
                            self.point_acquired.emit(x, y, z)

            # ════════════════════════════════════════════════════════
            # RETORNO AL ORIGEN (siempre, incluso si se aborta)
            # ════════════════════════════════════════════════════════
            print("Retornando motores al origen...")
            if self.use_x:
                self.mot.goto_and_wait(1, self.xin)
            if self.use_y:
                self.mot.goto_and_wait(2, self.yin)
            if self.use_z:
                self.mot.goto_and_wait(3, self.zin)
            print("✓ Motores en posición inicial")

        except MotorError as e:
            self.error_occurred.emit(str(e))
            return
        except Exception as e:
            self.error_occurred.emit(f"Error inesperado: {str(e)}")
            return
        
        # Emitir señal apropiada según si se abortó o terminó
        if self._abort_flag:
            print("⚠️  Barrido ABORTADO por usuario")
            self.aborted.emit()
        else:
            self.finished.emit()


# ============================================================
# GUI PRINCIPAL - MEJORADA
# ============================================================
class OCTGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OCT Python VL - Powered by the light side")
        self.resize(1500, 900)

        # -------- Hardware
        try:
            self.spec = HRSpectrometer()
            self.spec.connect()
            print("✓ Espectrómetro conectado")
        except Exception as e:
            print(f"⚠ Error conectando espectrómetro: {e}")
            self.spec = None

        try:
            self.mot = ESP301("COM3")
            self.mot.connect()
            
            # FORZAR respuesta del controlador
            self.mot.send("*IDN?\r")
            resp = self.mot.read()
            
            if not resp:
                raise RuntimeError("ESP301 no responde")
            # =========================================
            # Detectar ejes realmente disponibles
            # =========================================
            self.available_axes = set()
            
            for axis in (1, 2, 3):
                try:
                    resp = self.mot.send(f"{axis}TP?")
                    if resp is not None and resp != "":
                        float(resp)  # fuerza validación numérica
                        self.available_axes.add(axis)
                except:
                    pass
            
            axis_names = {1: "X", 2: "Y", 3: "Z"}
            detected = [axis_names[a] for a in sorted(self.available_axes)]
            
            print("✓ Motores conectados")
            print(f"✓ Ejes detectados: {detected}")
            
        except Exception as e:
            print(f"⚠ Error conectando motores: {e}")
            self.mot = None

        # -------- Buffers de barrido
        self.scan_x = []
        self.scan_y = []
        self.scan_z = []  # NUEVO: coordenadas Z
        self.scan_spectra = []
        self.scan_fft = []
        self.scan_win_opd = []
        self.scan_win_amp = []
        self.scan_wavelengths = None
        self.scan_opd = None
        
        # NUEVO v1.0.0: Saver para formato estandarizado
        self.saver = OCTDataSaver()
        print(f"✓ Saver inicializado (schema v{self.saver.schema_version})")
        
        # NUEVO v1.0.0: Control de guardados parciales
        self.enable_partial_saves = False  # Será actualizado por checkbox
        self.partial_save_interval = 0.10  # 10% del progreso
        self._last_partial_save_percent = 0.0
        self._n_points_total = 0
        self._start_time = None
        self._partial_counter = 0
        
        # OPT A1: Worker de barrido (para detectar si está en curso)
        self.worker = None
        
        # OPT #4: Array reutilizable para picos (evitar allocations en loop)
        self._temp_win_opd = np.full((MAX_WINDOWS, PEAKS_PER_WINDOW), np.nan)
        self._temp_win_amp = np.full((MAX_WINDOWS, PEAKS_PER_WINDOW), np.nan)

        # -------- Parámetros de procesamiento
        self.use_cubic_interp = True  # Interpolación cúbica por defecto
        self.current_wl = None
        self.current_intens = None
        
        # OPT A2: Lista de ventanas activas (pre-calculadas en run_scan)
        self._active_windows = []
        
        # -------- Cache para optimización (OPT #2, #3)
        self._cache_wl = None      # Wavelengths en metros
        self._cache_k = None       # k-space
        self._cache_k_lin = None   # k-space linearizado
        self._cache_interp_obj = None  # Objeto de interpolación cúbica
        self._cache_dk = None      # Delta k
        self._cache_fs = None      # Frecuencia de muestreo

        # -------- Timer para adquisición continua
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)

        # -------- GUI
        self._setup_ui()

    def _setup_ui(self):
        """Configurar interfaz de usuario"""
        central = QWidget()
        self.setCentralWidget(central)
        main = QHBoxLayout(central)

        # ================= LEFT PANEL (con scroll) =================
        # Crear widget contenedor para el panel izquierdo
        left_widget = QWidget()
        left = QVBoxLayout(left_widget)
        left.setContentsMargins(5, 5, 5, 5)  # Márgenes pequeños
        
        # Crear scroll area
        scroll = QScrollArea()
        scroll.setWidget(left_widget)
        scroll.setWidgetResizable(True)  # Importante: permite que el contenido se ajuste
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # Solo scroll vertical
        scroll.setMinimumWidth(420)  # Ancho mínimo para que se vea bien
        
        # Agregar scroll area al layout principal
        main.addWidget(scroll, 1)

        # ---- Adquisición
        g_acq = QGroupBox("Adquisición")
        la = QGridLayout(g_acq)

        la.addWidget(QLabel("Exposición (ms)"), 0, 0)
        self.spin_exp = QDoubleSpinBox()
        self.spin_exp.setRange(0.1, 2000)
        self.spin_exp.setValue(10)
        self.spin_exp.setDecimals(1)
        la.addWidget(self.spin_exp, 0, 1)

        self.chk_dark = QCheckBox("Dark correction")
        self.chk_lin = QCheckBox("Linearity correction")

        la.addWidget(QPushButton("Start", clicked=self.start_acq), 1, 0)
        la.addWidget(QPushButton("Stop", clicked=self.stop_acq), 1, 1)
        la.addWidget(self.chk_dark, 2, 0)
        la.addWidget(self.chk_lin, 2, 1)

        # Opción de interpolación
        self.chk_cubic = QCheckBox("Interpolación cúbica (mejor calidad)")
        self.chk_cubic.setChecked(True)
        self.chk_cubic.stateChanged.connect(self._toggle_interp)
        la.addWidget(self.chk_cubic, 3, 0, 1, 2)
        
        # Opción de CZT por ventanas
        self.chk_czt_windows = QCheckBox("CZT por ventanas (más preciso)")
        self.chk_czt_windows.setChecked(False)
        self.chk_czt_windows.setToolTip("Aplica CZT solo en ventanas activas para mayor precisión\n⚠ No compatible con interpolación cúbica")
        self.chk_czt_windows.stateChanged.connect(self._toggle_czt_windows)
        la.addWidget(self.chk_czt_windows, 4, 0, 1, 2)

        # Info de resolución
        self.lbl_resolution = QLabel("Resolución: -- um")
        la.addWidget(self.lbl_resolution, 5, 0, 1, 2)

        left.addWidget(g_acq)

        # ---- Ventanas OPD
        g_win = QGroupBox("Ventanas OPD (mm)")
        lw = QGridLayout(g_win)

        lw.addWidget(QLabel("Enable"), 0, 0)
        lw.addWidget(QLabel("Min"), 0, 1)
        lw.addWidget(QLabel("Max"), 0, 2)

        self.win_enable = []
        self.win_min = []
        self.win_max = []

        for i in range(MAX_WINDOWS):
            chk = QCheckBox(f"W{i+1}")
            sp_min = QDoubleSpinBox()
            sp_max = QDoubleSpinBox()
            sp_min.setRange(0, 10)
            sp_max.setRange(0, 10)
            sp_min.setDecimals(4)
            sp_max.setDecimals(4)
            
            # Valores por defecto escalonados
            sp_min.setValue(i * 0.5)
            sp_max.setValue((i + 1) * 0.5)

            lw.addWidget(chk, i+1, 0)
            lw.addWidget(sp_min, i+1, 1)
            lw.addWidget(sp_max, i+1, 2)

            self.win_enable.append(chk)
            self.win_min.append(sp_min)
            self.win_max.append(sp_max)

        # Habilitar primera ventana por defecto
        self.win_enable[0].setChecked(True)

        left.addWidget(g_win)

        # ---- Selector de visualización
        g_view = QGroupBox("Visualización FFT")
        lv = QGridLayout(g_view)

        lv.addWidget(QLabel("Ventana"), 0, 0)
        self.view_window = QDoubleSpinBox()
        self.view_window.setRange(1, MAX_WINDOWS)
        self.view_window.setDecimals(0)
        self.view_window.setValue(1)
        lv.addWidget(self.view_window, 0, 1)

        lv.addWidget(QLabel("Pico"), 1, 0)
        self.view_peak = QDoubleSpinBox()
        self.view_peak.setRange(1, PEAKS_PER_WINDOW)
        self.view_peak.setDecimals(0)
        self.view_peak.setValue(1)
        lv.addWidget(self.view_peak, 1, 1)

        # Mostrar valor del pico seleccionado
        self.lbl_peak_value = QLabel("OPD: -- um")
        lv.addWidget(self.lbl_peak_value, 2, 0, 1, 2)

        left.addWidget(g_view)

        # ---- Movimiento Manual de Motores
        g_manual = QGroupBox("Movimiento Manual")
        lm = QGridLayout(g_manual)
        
        # Eje X
        lm.addWidget(QLabel("X (mm)"), 0, 0)
        self.manual_x_pos = QDoubleSpinBox()
        self.manual_x_pos.setRange(-100, 100)
        self.manual_x_pos.setDecimals(3)
        self.manual_x_pos.setValue(0)
        lm.addWidget(self.manual_x_pos, 0, 1)
        lm.addWidget(QPushButton("Mover X", clicked=self.move_x_manual), 0, 2)
        
        # Eje Y
        lm.addWidget(QLabel("Y (mm)"), 1, 0)
        self.manual_y_pos = QDoubleSpinBox()
        self.manual_y_pos.setRange(-100, 100)
        self.manual_y_pos.setDecimals(3)
        self.manual_y_pos.setValue(0)
        lm.addWidget(self.manual_y_pos, 1, 1)
        lm.addWidget(QPushButton("Mover Y", clicked=self.move_y_manual), 1, 2)
        
        # Eje Z (NUEVO)
        lm.addWidget(QLabel("Z (mm)"), 2, 0)
        self.manual_z_pos = QDoubleSpinBox()
        self.manual_z_pos.setRange(-100, 100)
        self.manual_z_pos.setDecimals(3)
        self.manual_z_pos.setValue(0)
        lm.addWidget(self.manual_z_pos, 2, 1)
        lm.addWidget(QPushButton("Mover Z", clicked=self.move_z_manual), 2, 2)
        
        # Botones rápidos
        lm.addWidget(QPushButton("Home (0,0,0)", clicked=self.move_home), 3, 0)
        lm.addWidget(QPushButton("Enable X", clicked=lambda: self.enable_motor(1)), 3, 1)
        lm.addWidget(QPushButton("Enable Y", clicked=lambda: self.enable_motor(2)), 3, 2)
        
        # NUEVO: Enable Z
        lm.addWidget(QPushButton("Enable Z", clicked=lambda: self.enable_motor(3)), 4, 0)
        
        # Posición actual
        self.lbl_pos_actual = QLabel("Posición: --")
        lm.addWidget(self.lbl_pos_actual, 5, 0, 1, 3)
        
        left.addWidget(g_manual)
        
        # ---- Barrido
        g_scan = QGroupBox("Barrido")
        ls = QGridLayout(g_scan)

        # Eje X
        self.scan_x_in = QDoubleSpinBox()
        self.scan_x_in.setRange(-100, 100)
        self.scan_x_in.setDecimals(3)
        
        self.scan_x_end = QDoubleSpinBox()
        self.scan_x_end.setRange(-100, 100)
        self.scan_x_end.setDecimals(3)
        self.scan_x_end.setValue(1.0)
        
        self.scan_x_step = QDoubleSpinBox()
        self.scan_x_step.setRange(0.001, 10)
        self.scan_x_step.setValue(0.1)
        self.scan_x_step.setDecimals(3)
        
        self.chk_scan_x = QCheckBox("Usar X")

        # Eje Y
        self.scan_y_in = QDoubleSpinBox()
        self.scan_y_in.setRange(-100, 100)
        self.scan_y_in.setDecimals(3)
        
        self.scan_y_end = QDoubleSpinBox()
        self.scan_y_end.setRange(-100, 100)
        self.scan_y_end.setDecimals(3)
        
        self.scan_y_step = QDoubleSpinBox()
        self.scan_y_step.setRange(0.001, 10)
        self.scan_y_step.setValue(0.1)
        self.scan_y_step.setDecimals(3)
        
        self.chk_scan_y = QCheckBox("Usar Y")

        # Eje Z (NUEVO)
        self.scan_z_in = QDoubleSpinBox()
        self.scan_z_in.setRange(-100, 100)
        self.scan_z_in.setDecimals(3)
        
        self.scan_z_end = QDoubleSpinBox()
        self.scan_z_end.setRange(-100, 100)
        self.scan_z_end.setDecimals(3)
        
        self.scan_z_step = QDoubleSpinBox()
        self.scan_z_step.setRange(0.001, 10)
        self.scan_z_step.setValue(0.1)
        self.scan_z_step.setDecimals(3)
        
        self.chk_scan_z = QCheckBox("Usar Z")

        # Layout
        ls.addWidget(QLabel("X in"), 0, 0)
        ls.addWidget(self.scan_x_in, 0, 1)
        ls.addWidget(QLabel("X end"), 0, 2)
        ls.addWidget(self.scan_x_end, 0, 3)
        ls.addWidget(QLabel("step"), 0, 4)
        ls.addWidget(self.scan_x_step, 0, 5)
        ls.addWidget(self.chk_scan_x, 0, 6)

        ls.addWidget(QLabel("Y in"), 1, 0)
        ls.addWidget(self.scan_y_in, 1, 1)
        ls.addWidget(QLabel("Y end"), 1, 2)
        ls.addWidget(self.scan_y_end, 1, 3)
        ls.addWidget(QLabel("step"), 1, 4)
        ls.addWidget(self.scan_y_step, 1, 5)
        ls.addWidget(self.chk_scan_y, 1, 6)
        
        # NUEVO: Fila para Z
        ls.addWidget(QLabel("Z in"), 2, 0)
        ls.addWidget(self.scan_z_in, 2, 1)
        ls.addWidget(QLabel("Z end"), 2, 2)
        ls.addWidget(self.scan_z_end, 2, 3)
        ls.addWidget(QLabel("step"), 2, 4)
        ls.addWidget(self.scan_z_step, 2, 5)
        ls.addWidget(self.chk_scan_z, 2, 6)
        
        # Settling time (tiempo de asentamiento)
        ls.addWidget(QLabel("Settling (ms):"), 3, 0)
        self.scan_settling = QDoubleSpinBox()
        self.scan_settling.setRange(0, 500)
        self.scan_settling.setValue(50)  # Default: 50ms
        self.scan_settling.setSingleStep(10)
        self.scan_settling.setDecimals(0)
        self.scan_settling.setToolTip("Tiempo de espera despues de que el motor llega,\npara que se disipen las vibraciones")
        ls.addWidget(self.scan_settling, 3, 1, 1, 2)
        
        # NUEVO v1.0.0: Checkbox para guardados parciales
        self.chk_partial_saves = QCheckBox("💾 Guardados parciales (c/10%)")
        self.chk_partial_saves.setChecked(False)
        self.chk_partial_saves.setToolTip(
            "Guardar automáticamente cada 10% del progreso.\n"
            "Útil para barridos largos >1 hora.\n\n"
            "Los parciales son acumulativos:\n"
            "- Contienen TODOS los datos hasta ese punto\n"
            "- Formato: scan_YYYY-MM-DD_HH-MM_part_XXofYY.npz\n"
            "- Permiten recuperación si el barrido se interrumpe"
        )
        ls.addWidget(self.chk_partial_saves, 3, 3, 1, 4)

        # Botones de control de barrido
        self.btn_run_scan = QPushButton("▶ Ejecutar Barrido", clicked=self.run_scan)
        self.btn_abort_scan = QPushButton("⏹ ABORTAR", clicked=self.abort_scan)
        self.btn_abort_scan.setEnabled(False)  # Deshabilitado hasta que inicie barrido
        self.btn_abort_scan.setStyleSheet("background-color: #ff6b6b; font-weight: bold;")
        
        ls.addWidget(self.btn_run_scan, 4, 0, 1, 3)
        ls.addWidget(self.btn_abort_scan, 4, 3, 1, 4)
        
        self.lbl_scan_progress = QLabel("Listo")
        ls.addWidget(self.lbl_scan_progress, 5, 0, 1, 7)

        left.addWidget(g_scan)
        
        # ---- OPT A1: Control de visualización durante barrido
        g_vis = QGroupBox("Control de Visualización")
        lv = QVBoxLayout(g_vis)
        
        # Checkbox para pausar plots
        self.chk_pause_plots = QCheckBox("⏸ Pausar gráficos durante barrido")
        self.chk_pause_plots.setChecked(False)  # Default: plots ACTIVOS
        self.chk_pause_plots.setStyleSheet("""
            QCheckBox {
                font-weight: bold;
                color: #FFA500;
            }
        """)
        self.chk_pause_plots.setToolTip(
            "Desactiva TODOS los gráficos durante barridos.\n\n"
            "Qué se pausa:\n"
            "  • Timer de actualización en tiempo real (100ms)\n"
            "  • Gráficos de Espectro y FFT (derecha)\n"
            "  • Actualización de plots durante barrido\n\n"
            "✓ Ventajas:\n"
            "  • 5-10% más rápido (~2-3 min en barridos grandes)\n"
            "  • Menos carga en CPU/GPU\n"
            "  • Reduce lag en la interfaz\n\n"
            "✗ Desventajas:\n"
            "  • No ves progreso visual en tiempo real\n"
            "  • Pantalla congelada durante barrido\n\n"
            "IMPORTANTE: Los datos siempre se guardan correctamente,\n"
            "solo se pausa la visualización.\n\n"
            "Al finalizar el barrido, todo se reanuda automáticamente."
        )
        
        # Label de estado
        self.lbl_plot_status = QLabel("Estado plots: 🟢 ACTIVOS")
        self.lbl_plot_status.setStyleSheet("color: green; font-weight: bold;")
        
        # Conectar señal para actualizar estado visual
        self.chk_pause_plots.stateChanged.connect(self.on_pause_plots_changed)
        
        lv.addWidget(self.chk_pause_plots)
        lv.addWidget(self.lbl_plot_status)
        
        left.addWidget(g_vis)

        # ================= RIGHT PANEL =================
        right = QVBoxLayout()
        main.addLayout(right, 2)

        # Plots
        self.plot_spec = pg.PlotWidget(title="Espectro")
        self.plot_spec.setLabel('left', 'Intensidad')
        self.plot_spec.setLabel('bottom', 'Longitud de onda', units='nm')
        self.plot_spec.showGrid(x=True, y=True, alpha=0.3)

        self.plot_fft = pg.PlotWidget(title="FFT (OPD)")
        self.plot_fft.setLabel('left', 'Amplitud')
        self.plot_fft.setLabel('bottom', 'OPD', units='mm')
        self.plot_fft.showGrid(x=True, y=True, alpha=0.3)

        right.addWidget(self.plot_spec)
        right.addWidget(self.plot_fft)

    # ============================================================
    # OPT A1: Manejo de estado de visualización
    # ============================================================
    def on_pause_plots_changed(self, state):
        """
        Actualizar indicador cuando cambia estado de plots.
        NUEVO: También maneja cambio DURANTE el barrido.
        """
        is_paused = self.chk_pause_plots.isChecked()
        
        # Actualizar indicador visual
        if is_paused:
            self.lbl_plot_status.setText("Estado plots: 🔴 PAUSADOS")
            self.lbl_plot_status.setStyleSheet("color: red; font-weight: bold;")
        else:
            self.lbl_plot_status.setText("Estado plots: 🟢 ACTIVOS")
            self.lbl_plot_status.setStyleSheet("color: green; font-weight: bold;")
        
        # ════════════════════════════════════════════════════════
        # NUEVO: Si hay un barrido en curso, aplicar cambio inmediatamente
        # ════════════════════════════════════════════════════════
        is_scanning = hasattr(self, 'worker') and self.worker is not None and self.worker.isRunning()
        
        if is_scanning:
            if is_paused:
                # Usuario marcó checkbox DURANTE barrido → Pausar timer
                if self.timer.isActive():
                    self.timer.stop()
                    print("⏸ Timer pausado (durante barrido)")
            else:
                # Usuario desmarcó checkbox DURANTE barrido → Reanudar timer
                if not self.timer.isActive():
                    self.timer.start(100)
                    print("▶ Timer reanudado (durante barrido)")
    
    # ============================================================
    # Movimiento manual de motores
    # ============================================================
    def move_x_manual(self):
        """Mover eje X a posición manual"""
        if self.mot is None:
            QMessageBox.warning(self, "Error", "Motores no conectados")
            return
        if 1 not in self.available_axes:
            QMessageBox.warning(self, "Error", "Eje X no disponible")
            return
        try:
            pos = self.manual_x_pos.value()
            self.mot.goto_and_wait(1, pos)
            actual = self.mot.get_position(1)
            self.lbl_pos_actual.setText(f"Posición: X={actual:.3f}")
            print(f"✓ X movido a {actual:.3f} mm")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error moviendo X: {e}")
    
    def move_y_manual(self):
        """Mover eje Y a posición manual"""
        if self.mot is None:
            QMessageBox.warning(self, "Error", "Motores no conectados")
            return
        if 2 not in self.available_axes:
            QMessageBox.warning(self, "Error", "Eje Y no disponible")
            return

        try:
            pos = self.manual_y_pos.value()
            self.mot.goto_and_wait(2, pos)
            actual = self.mot.get_position(2)
            self.lbl_pos_actual.setText(f"Posición: Y={actual:.3f}")
            print(f"✓ Y movido a {actual:.3f} mm")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error moviendo Y: {e}")
    
    def move_z_manual(self):
        """Mover eje Z a posición manual (NUEVO)"""
        if self.mot is None:
            QMessageBox.warning(self, "Error", "Motores no conectados")
            return
        if 3 not in self.available_axes:
            QMessageBox.warning(self, "Error", "Eje Z no disponible")
            return

        try:
            pos = self.manual_z_pos.value()
            self.mot.goto_and_wait(3, pos)
            actual = self.mot.get_position(3)
            self.lbl_pos_actual.setText(f"Posición: Z={actual:.3f}")
            print(f"✓ Z movido a {actual:.3f} mm")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error moviendo Z: {e}")
    
    def move_home(self):
        """Mover todos los ejes a posición (0,0,0)"""
        if self.mot is None:
            QMessageBox.warning(self, "Error", "Motores no conectados")
            return
        
        try:
            if 1 in self.available_axes:
                self.mot.goto_and_wait(1, 0.0)
            if 2 in self.available_axes:
                self.mot.goto_and_wait(2, 0.0)
            if 3 in self.available_axes:
                self.mot.goto_and_wait(3, 0.0)
            parts = []
            if 1 in self.available_axes:
                parts.append(f"X={self.mot.get_position(1):.3f}")
            if 2 in self.available_axes:
                parts.append(f"Y={self.mot.get_position(2):.3f}")
            if 3 in self.available_axes:
                parts.append(f"Z={self.mot.get_position(3):.3f}")
            
            self.lbl_pos_actual.setText("Posición: " + ", ".join(parts))
            print(f"✓ Motores en home: {', '.join(parts)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error en home: {e}")
    
    def enable_motor(self, axis):
        """Habilitar motor especificado"""
        if self.mot is None:
            QMessageBox.warning(self, "Error", "Motores no conectados")
            return
         # ⛔ Bloqueo por eje inexistente
        if axis not in self.available_axes:
            axis_name = {1: "X", 2: "Y", 3: "Z"}.get(axis, "?")
            QMessageBox.warning(
                self,
                "Eje no disponible",
                f"El eje {axis_name} no está conectado o no responde."
            )
            return
    
        try:
            self.mot.enable_axis(axis)
            axis_name = {1: "X", 2: "Y", 3: "Z"}.get(axis, "?")
            print(f"✓ Motor {axis_name} habilitado")
            QMessageBox.information(self, "Éxito", f"Motor {axis_name} habilitado")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error habilitando motor: {e}")

    # ============================================================
    # Control de adquisición
    # ============================================================
    def start_acq(self):
        """Iniciar adquisición continua"""
        if self.spec is None:
            QMessageBox.warning(self, "Error", "Espectrómetro no conectado")
            return

        self.spec.set_exposure_ms(self.spin_exp.value())
        self.spec.dark_enabled = self.chk_dark.isChecked()
        self.spec.linearity_enabled = self.chk_lin.isChecked()
        self.timer.start(100)  # Actualizar cada 100 ms

    def stop_acq(self):
        """Detener adquisición"""
        self.timer.stop()

    def _toggle_interp(self, state):
        """Toggle entre interpolación lineal y cúbica"""
        self.use_cubic_interp = state == 2  # Qt.Checked = 2
        
        # Si activo cúbica, desactivar CZT (son incompatibles)
        if self.use_cubic_interp and self.chk_czt_windows.isChecked():
            self.chk_czt_windows.blockSignals(True)  # Evitar recursión
            self.chk_czt_windows.setChecked(False)
            self.chk_czt_windows.blockSignals(False)
    
    def _toggle_czt_windows(self, state):
        """Toggle CZT por ventanas"""
        # Si activo CZT, desactivar interpolación cúbica (son incompatibles)
        if state == 2 and self.chk_cubic.isChecked():  # Qt.Checked = 2
            self.chk_cubic.blockSignals(True)  # Evitar recursión
            self.chk_cubic.setChecked(False)
            self.chk_cubic.blockSignals(False)
            self.use_cubic_interp = False

    # ============================================================
    # Procesamiento mejorado con CZT por ventanas + OPTIMIZADO
    # ============================================================
    def _update_cache(self, wl):
        """
        OPT #2: Actualizar cache de k-space solo si wavelengths cambian
        """
        wl_meters = wl * 1e-9 if not isinstance(wl, np.ndarray) else wl * 1e-9
        
        # Verificar si necesitamos actualizar cache
        if (self._cache_wl is None or 
            len(self._cache_wl) != len(wl_meters) or
            not np.allclose(self._cache_wl, wl_meters)):
            
            # OPT #6: Evitar conversión redundante
            self._cache_wl = wl_meters
            
            # Calcular k-space
            k = 2 * np.pi / wl_meters
            self._cache_k = np.flip(k)
            
            # Linearizar
            self._cache_k_lin = np.linspace(self._cache_k[0], self._cache_k[-1], len(self._cache_k))
            
            # Pre-calcular constantes
            self._cache_dk = np.mean(np.diff(self._cache_k_lin))
            self._cache_fs = 1.0 / (self._cache_dk / (2 * np.pi))
            
            # Invalidar cache de interpolación
            self._cache_interp_obj = None
    
    def compute_fft_full(self, wl, intens):
        """
        Procesamiento FFT completo OPTIMIZADO
        OPT #2: Cache k-space, OPT #3: Cache interpolación, OPT #6: Sin conversiones redundantes
        """
        # OPT #2: Actualizar cache solo si es necesario
        self._update_cache(wl)
        
        # OPT #6: Trabajar directo con arrays (ya vienen de numpy)
        s = intens if isinstance(intens, np.ndarray) else np.array(intens)
        s = np.flip(s)

        # OPT #3: Interpolación CÚBICA con cache
        if self.use_cubic_interp:
            try:
                # Reconstruir objeto solo si cambió k (raro) o es primera vez
                if self._cache_interp_obj is None:
                    # Pre-construir matriz de interpolación (se reutiliza)
                    self._cache_interp_obj = interp1d(
                        self._cache_k, 
                        self._cache_k,  # Dummy, se reemplaza cada vez
                        kind='cubic', 
                        fill_value='extrapolate',
                        assume_sorted=True  # OPT: k está ordenado
                    )
                
                # Usar interpolación lineal rápida en su lugar
                # (interp1d no cachea bien, usar método más eficiente)
                from scipy.interpolate import CubicSpline
                cs = CubicSpline(self._cache_k, s, extrapolate=True)
                s_lin = cs(self._cache_k_lin)
            except:
                # Fallback a lineal si falla
                s_lin = np.interp(self._cache_k_lin, self._cache_k, s)
        else:
            # Interpolación lineal (ya optimizada por numpy)
            s_lin = np.interp(self._cache_k_lin, self._cache_k, s)

        # FFT
        fft_result = np.fft.fft(s_lin)
        amp = np.abs(fft_result)

        # OPT #2: Usar dk pre-calculado
        opd = np.fft.fftfreq(len(amp), d=self._cache_dk/(2*np.pi))

        # Solo frecuencias positivas
        positive_idx = opd >= 0
        opd = opd[positive_idx]
        amp = amp[positive_idx]

        return opd, amp, s_lin, self._cache_k_lin
    
    def compute_fft_windows(self, wl, intens):
        """
        Procesamiento CZT aplicado solo en ventanas activas OPTIMIZADO
        OPT #1: Import movido al inicio
        OPT #2: Cache k-space
        OPT #6: Sin conversiones
        P2: FORZAR interpolación LINEAL (CZT hace remuestreo fino)
        """
        # OPT #1: Ya no hace import aquí (está al inicio del archivo)
        
        # OPT #2: Usar cache
        self._update_cache(wl)
        
        # OPT #6: Trabajar directo con arrays
        s = intens if isinstance(intens, np.ndarray) else np.array(intens)
        s = np.flip(s)
        
        # P2: SIEMPRE usar interpolación LINEAL en modo CZT
        # Razón: CZT ya hace remuestreo fino, interpolación cúbica es redundante
        s_lin = np.interp(self._cache_k_lin, self._cache_k, s)
        
        # OPT #2: Usar fs pre-calculado
        fs = self._cache_fs
        
        # Procesar cada ventana activa con CZT
        window_results = {}
        
        for w in range(MAX_WINDOWS):
            if not self.win_enable[w].isChecked():
                continue
            
            # Límites de la ventana en metros
            f1 = self.win_min[w].value() * 1e-3
            f2 = self.win_max[w].value() * 1e-3
            
            if f2 <= f1:
                continue
            
            # Calcular número de puntos óptimo para esta ventana
            npoints = 2048  # Ajustable según necesidad
            
            try:
                # Aplicar CZT solo en este rango
                z, fz = czt_zoom(s_lin, f1, f2, fs, npoints)
                amp = np.abs(z)
                
                window_results[w] = {
                    'opd': fz,
                    'amp': amp,
                    'z': z
                }
            except Exception as e:
                print(f"Error en CZT ventana {w}: {e}")
                continue
        
        return window_results

    # ELIMINADO P1: compute_fft() wrapper engañoso
    # Usar llamadas directas:
    # - compute_fft_full() para FFT tradicional
    # - compute_fft_windows() para CZT por ventanas

    # ============================================================
    # Actualización de datos en tiempo real
    # ============================================================
    def update_data(self):
        """Actualizar datos y gráficos"""
        if self.spec is None:
            return

        try:
            wl, intens = self.spec.read()
            
            if wl is None or intens is None:
                return

            # Guardar para uso posterior
            self.current_wl = wl
            self.current_intens = intens

            # Calcular y mostrar resolución
            if len(wl) > 0:
                res = calculate_resolution(wl[0], wl[-1])
                self.lbl_resolution.setText(f"Resolución: {res:.2f} um")

            # Plot espectro
            self.plot_spec.plot(wl, intens, clear=True, pen='w')

            # Decidir qué método de FFT usar
            use_czt_windows = self.chk_czt_windows.isChecked()
            
            if use_czt_windows:
                # Modo CZT por ventanas
                self._update_with_czt_windows(wl, intens)
            else:
                # Modo FFT tradicional (completo)
                self._update_with_full_fft(wl, intens)

        except Exception as e:
            print(f"Error en update_data: {e}")
    
    def _update_with_full_fft(self, wl, intens):
        """Actualización con FFT completo (modo tradicional)"""
        # P1: Llamada directa a compute_fft_full()
        opd, amp, _, _ = self.compute_fft_full(wl, intens)

        # FFT completa (gris claro)
        self.plot_fft.plot(opd * 1e3, amp, clear=True, pen=(150, 150, 150))

        # Selector de ventana + pico
        w = int(self.view_window.value()) - 1
        p = int(self.view_peak.value()) - 1

        if w < MAX_WINDOWS and self.win_enable[w].isChecked():
            o0 = self.win_min[w].value() * 1e-3  # Convertir mm a m
            o1 = self.win_max[w].value() * 1e-3

            # Detectar picos en ventana
            locs, pks, _ = detect_peaks_in_window(
                amp + 0j,  # Convertir a complejo
                opd,
                o0, o1,
                nmax=PEAKS_PER_WINDOW,
                min_width=3e-6
            )

            # Dibujar ventana activa
            mask = (opd >= o0) & (opd <= o1)
            if np.any(mask):
                self.plot_fft.plot(opd[mask] * 1e3, amp[mask], 
                                  pen='y', width=2)

            # Marcar pico seleccionado
            if p < len(locs):
                self.plot_fft.plot(
                    [locs[p] * 1e3],
                    [pks[p]],
                    pen=None,
                    symbol='o',
                    symbolBrush='r',
                    symbolSize=10
                )
                self.lbl_peak_value.setText(f"OPD: {locs[p]*1e6:.2f} um")
            else:
                self.lbl_peak_value.setText("OPD: --")
    
    def _update_with_czt_windows(self, wl, intens):
        """Actualización con CZT por ventanas (modo optimizado)"""
        # Procesar ventanas con CZT
        window_results = self.compute_fft_windows(wl, intens)
        
        # Limpiar plot
        self.plot_fft.clear()
        
        # Selector de ventana actual
        w = int(self.view_window.value()) - 1
        p = int(self.view_peak.value()) - 1
        
        # Dibujar todas las ventanas activas
        colors = ['y', 'c', 'm', 'g', 'r']
        
        for win_idx, win_data in window_results.items():
            opd = win_data['opd']
            amp = win_data['amp']
            
            # Color según si es la ventana seleccionada
            if win_idx == w:
                pen = pg.mkPen(color=colors[win_idx % len(colors)], width=2)
            else:
                pen = pg.mkPen(color=(100, 100, 100), width=1)
            
            self.plot_fft.plot(opd * 1e3, amp, pen=pen)
        
        # Detectar y marcar picos en ventana seleccionada
        if w in window_results:
            win_data = window_results[w]
            opd = win_data['opd']
            amp = win_data['amp']
            
            # Detectar picos
            locs, pks, _ = detect_peaks_in_window(
                win_data['z'],
                opd,
                opd[0], opd[-1],  # Toda la ventana
                nmax=PEAKS_PER_WINDOW,
                min_width=3e-6
            )
            
            # Marcar pico seleccionado
            if p < len(locs):
                self.plot_fft.plot(
                    [locs[p] * 1e3],
                    [pks[p]],
                    pen=None,
                    symbol='o',
                    symbolBrush='r',
                    symbolSize=12
                )
                self.lbl_peak_value.setText(f"OPD: {locs[p]*1e6:.2f} um [CZT]")
            else:
                self.lbl_peak_value.setText("OPD: -- [CZT]")
        else:
            self.lbl_peak_value.setText("Ventana no activa")

    # ============================================================
    # Barrido
    # ============================================================
    def run_scan(self):
        """Ejecutar barrido automático (1D, 2D o 3D)"""
        if self.mot is None:
            QMessageBox.warning(self, "Error", "Motores no conectados")
            return
    
        # Verificar que al menos un eje esté seleccionado
        if not self.chk_scan_x.isChecked() and not self.chk_scan_y.isChecked() and not self.chk_scan_z.isChecked():
            QMessageBox.warning(self, "Error", "Seleccione al menos un eje")
            return
        axis_map = {
            1: ("X", self.chk_scan_x),
            2: ("Y", self.chk_scan_y),
            3: ("Z", self.chk_scan_z),
        }
        
        for axis, (name, chk) in axis_map.items():
            if chk.isChecked() and axis not in self.available_axes:
                QMessageBox.critical(
                    self,
                    "Error de configuración",
                    f"El eje {name} fue seleccionado pero no está conectado."
                )
                return

        # Limpiar buffers
        self.scan_x.clear()
        self.scan_y.clear()
        self.scan_z.clear()
        self.scan_spectra.clear()
        self.scan_fft.clear()
        self.scan_win_opd.clear()
        self.scan_win_amp.clear()
        self.scan_wavelengths = None
        self.scan_opd = None
    
        # === Sincronización: detener SIEMPRE el QTimer durante el barrido ===
        self._timer_was_active = self.timer.isActive()
        if self._timer_was_active:
            self.timer.stop()
            print("⏸ QTimer detenido durante el barrido (evita lecturas concurrentes)")
    
        # === Ventanas activas (pre-cálculo) ===
        self._active_windows = []
        for w in range(MAX_WINDOWS):
            if self.win_enable[w].isChecked():
                self._active_windows.append({
                    'index': w,
                    'min': self.win_min[w].value() * 1e-3,
                    'max': self.win_max[w].value() * 1e-3,
                    'color': ['y', 'c', 'm', 'g', 'r'][w]
                })
        if len(self._active_windows) > 0:
            print(f"✓ Pre-calculadas {len(self._active_windows)} ventanas activas:")
            for win in self._active_windows:
                print(f"  W{win['index']+1}: {win['min']*1e3:.1f}-{win['max']*1e3:.1f} mm")
        else:
            print("⚠ No hay ventanas activas")
    
        # === Guardados parciales: activar y reset ===
        self.enable_partial_saves = self.chk_partial_saves.isChecked()
        self._last_partial_save_percent = 0.0
        self._partial_counter = 0
        self._points_acquired = 0  # ← contador real de puntos adquiridos
        self._start_time = datetime.now()
    
        # Calcular número total de puntos
        def count_points(use, start, end, step):
            if not use:
                return 1
            if step == 0:
                return 1
            return int(abs((end - start) / abs(step))) + 1

        nx = count_points(self.chk_scan_x.isChecked(), self.scan_x_in.value(), self.scan_x_end.value(), self.scan_x_step.value())
        ny = count_points(self.chk_scan_y.isChecked(), self.scan_y_in.value(), self.scan_y_end.value(), self.scan_y_step.value())
        nz = count_points(self.chk_scan_z.isChecked(), self.scan_z_in.value(), self.scan_z_end.value(), self.scan_z_step.value())
        self._n_points_total = nx * ny * nz
    
        if self.enable_partial_saves:
            n_partials = int(1.0 / self.partial_save_interval)
            print("💾 Guardados parciales ACTIVADOS:")
            print(f"  Intervalo: {self.partial_save_interval*100:.0f}%")
            print(f"  Total puntos: {self._n_points_total}")
            print(f"  Guardados esperados (aprox.): {n_partials}")
    
        # Crear worker
        settling_ms = self.scan_settling.value()
        settling_s = settling_ms / 1000.0
        self.worker = ScanWorker(
            self.mot,
            self.chk_scan_x.isChecked(),
            self.chk_scan_y.isChecked(),
            self.chk_scan_z.isChecked(),
            self.scan_x_in.value(),
            self.scan_x_end.value(),
            self.scan_x_step.value(),
            self.scan_y_in.value(),
            self.scan_y_end.value(),
            self.scan_y_step.value(),
            self.scan_z_in.value(),
            self.scan_z_end.value(),
            self.scan_z_step.value(),
            settling_time=settling_s
        )
        self.worker.point_acquired.connect(self.on_scan_point)
        self.worker.finished.connect(self.on_scan_finished)
        self.worker.error_occurred.connect(self.on_scan_error)
        self.worker.aborted.connect(self.on_scan_aborted)
    
        # Estado UI
        self.btn_abort_scan.setEnabled(True)
        self.btn_run_scan.setEnabled(False)
        self.lbl_scan_progress.setText("Barrido en curso...")
    
        self.worker.start()

    def on_scan_point(self, x, y, z):  # MODIFICADO: ahora recibe z
        """
        Procesar punto del barrido con sincronización correcta:
        1. Motor llegó y settling mecánico completado (hecho en ScanWorker)
        2. READ 1: Descarta integración vieja (durante movimiento)
        3. WAIT t_exp: Nueva integración limpia
        4. READ 2: Esta SÍ es válida
    
        OPTIMIZACIONES:
        - A1: Control de visualización (pausar plots)
        - A2: Usa ventanas pre-calculadas (_active_windows)
        """
        if self.spec is None:
            return
        try:
            import time
            # --- ADQUISICIÓN ---
            _ = self.spec.read()  # READ 1: descartar
            t_exp_ms = self.spin_exp.value() if hasattr(self, 'spin_exp') else 10
            time.sleep(t_exp_ms / 1000.0)
            wl, intens = self.spec.read()  # READ 2: válida
            if wl is None or intens is None:
                return
    
            # Guardar wavelengths una sola vez
            if self.scan_wavelengths is None:
                self.scan_wavelengths = np.array(wl)
    
            # --- PROCESAMIENTO DSP ---
            use_czt_windows = self.chk_czt_windows.isChecked()
            if use_czt_windows:
                window_results = self.compute_fft_windows(wl, intens)
                if self.scan_opd is None:
                    self.scan_opd = {'mode': 'czt_windows', 'windows': {}}
                for w_idx, w_data in window_results.items():
                    self.scan_opd['windows'][w_idx] = w_data['opd']
    
                self._temp_win_opd.fill(np.nan)
                self._temp_win_amp.fill(np.nan)
                amp_full = None
    
                # Visualización (condicional)
                should_plot = not self.chk_pause_plots.isChecked()
                if should_plot:
                    self._update_czt_visualization(window_results)
    
                # Detección de picos y copia a buffers temporales
                for w in range(MAX_WINDOWS):
                    if w not in window_results:
                        continue
                    win_data = window_results[w]
                    opd = win_data['opd']
                    zc = win_data['z']
                    locs, pks, _ = detect_peaks_in_window(
                        zc, opd, opd[0], opd[-1],
                        nmax=PEAKS_PER_WINDOW,
                        min_width=3e-6
                    )
                    for i, (loc, pk) in enumerate(zip(locs, pks)):
                        self._temp_win_opd[w, i] = loc
                        self._temp_win_amp[w, i] = pk
            else:
                # FFT tradicional
                opd, amp, _, _ = self.compute_fft_full(wl, intens)
                if self.scan_opd is None:
                    self.scan_opd = opd
                amp_full = amp
    
                # Limpiar buffers temporales
                self._temp_win_opd.fill(np.nan)
                self._temp_win_amp.fill(np.nan)
    
                # Visualización (condicional)
                should_plot = not self.chk_pause_plots.isChecked()
                if should_plot:
                    self._update_fft_visualization(opd, amp)
    
                # Detección de picos en ventanas activas (pre-calculadas)
                for win_config in self._active_windows:
                    w = win_config['index']
                    o0 = win_config['min']
                    o1 = win_config['max']
                    locs, pks, _ = detect_peaks_in_window(
                        amp + 0j,
                        opd,
                        o0, o1,
                        nmax=PEAKS_PER_WINDOW,
                        min_width=3e-6
                    )
                    for i, (loc, pk) in enumerate(zip(locs, pks)):
                        self._temp_win_opd[w, i] = loc
                        self._temp_win_amp[w, i] = pk
    
            # --- GUARDADO DE ESTE PUNTO ---
            self.scan_x.append(x)
            self.scan_y.append(y)
            self.scan_z.append(z)
            self.scan_spectra.append(intens)
            if amp_full is not None:
                self.scan_fft.append(amp_full)
            self.scan_win_opd.append(self._temp_win_opd.copy())
            self.scan_win_amp.append(self._temp_win_amp.copy())
    
            # --- PROGRESO Y PARCIALES ---
            self._points_acquired += 1  # ← contador
            n_total = self._points_acquired
            self.lbl_scan_progress.setText(
                f"Punto {n_total}: X={x:.3f}, Y={y:.3f}, Z={z:.3f} mm"
            )
    
            if self.enable_partial_saves and self._n_points_total > 0:
                progress = self._points_acquired / self._n_points_total
                if progress - self._last_partial_save_percent >= self.partial_save_interval:
                    self._partial_counter += 1
                    parts_total = int(1.0 / self.partial_save_interval)
    
                    # Preparar y guardar (acumulativo)
                    scan_data = self._prepare_scan_data()
                    metadata = self._prepare_metadata()
                    filepath = generate_filename(
                        is_partial=True,
                        part_index=self._partial_counter,
                        parts_total=parts_total
                    )
                    self.saver.save_scan(
                        scan_data=scan_data,
                        metadata=metadata,
                        filepath=filepath,
                        is_partial=True,
                        part_index=self._partial_counter,
                        parts_total=parts_total
                    )
                    self._last_partial_save_percent = progress
                    print(f"💾 Guardado parcial {self._partial_counter} → {filepath}")
    
        except Exception as e:
            print(f"Error en scan point: {e}")
            import traceback
            traceback.print_exc()

    # ============================================================
    # OPT A1: Funciones de visualización separadas
    # ============================================================
    def _update_fft_visualization(self, opd, amp):
        """
        Actualizar visualización FFT durante barrido.
        Solo se llama si plots NO están pausados (OPT A1).
        """
        # Limpiar plot anterior
        self.plot_fft.clear()
        
        # Dibujar FFT completo (gris claro como fondo)
        self.plot_fft.plot(
            opd * 1e3,  # Convertir m -> mm
            amp,
            pen=(150, 150, 150),
            width=1
        )
        
        # Dibujar ventanas activas con colores (OPT A2: usar lista pre-calculada)
        for win_config in self._active_windows:
            w = win_config['index']
            o0 = win_config['min']
            o1 = win_config['max']
            color = win_config['color']
            
            # Máscara de ventana
            mask = (opd >= o0) & (opd <= o1)
            
            if np.any(mask):
                # Resaltar ventana activa
                self.plot_fft.plot(
                    opd[mask] * 1e3,
                    amp[mask],
                    pen=color,
                    width=2
                )
                
                # Marcar picos detectados
                for i in range(PEAKS_PER_WINDOW):
                    loc = self._temp_win_opd[w, i]
                    pk = self._temp_win_amp[w, i]
                    
                    if np.isfinite(loc) and np.isfinite(pk):
                        self.plot_fft.plot(
                            [loc * 1e3],  # mm
                            [pk],
                            pen=None,
                            symbol='o',
                            symbolBrush=color,
                            symbolSize=8
                        )
    
    def _update_czt_visualization(self, window_results):
        """
        Actualizar visualización CZT durante barrido.
        Solo se llama si plots NO están pausados (OPT A1).
        """
        self.plot_fft.clear()
        
        colors = ['y', 'c', 'm', 'g', 'r']
        
        for w_idx, win_data in window_results.items():
            opd = win_data['opd']
            z = win_data['z']
            amp = np.abs(z)
            
            # Dibujar FFT de esta ventana
            self.plot_fft.plot(
                opd * 1e3,
                amp,
                pen=colors[w_idx % len(colors)],
                width=2
            )
            
            # Marcar picos
            for i in range(PEAKS_PER_WINDOW):
                loc = self._temp_win_opd[w_idx, i]
                pk = self._temp_win_amp[w_idx, i]
                
                if np.isfinite(loc) and np.isfinite(pk):
                    self.plot_fft.plot(
                        [loc * 1e3],
                        [pk],
                        pen=None,
                        symbol='o',
                        symbolBrush=colors[w_idx % len(colors)],
                        symbolSize=10
                    )
    
    def on_scan_finished(self):
        """Finalizar barrido y guardar datos en formato v1.0.0"""
        try:
            # Reanudar QTimer SIEMPRE al finalizar
            if not self.timer.isActive():
                self.timer.start(100)
                print("▶ Gráficos reanudados al finalizar barrido")
            self.lbl_plot_status.setText("Estado plots: 🟢 ACTIVOS")
            self.lbl_plot_status.setStyleSheet("color: green; font-weight: bold;")
    
            # Restaurar estado de botones
            self.btn_abort_scan.setEnabled(False)
            self.btn_run_scan.setEnabled(True)
    
            # Limpiar referencia al worker
            self.worker = None
    
            # Guardado final (formato estandarizado)
            self._save_final_scan()
        except Exception as e:
            error_msg = f"Error al guardar: {e}"
            self.lbl_scan_progress.setText(error_msg)
            QMessageBox.critical(self, "Error", error_msg)
            print(error_msg)
            import traceback
            traceback.print_exc()
        # =====================================================
        # Guardado parcial FINAL forzado
        # =====================================================
        if self.enable_partial_saves:
            try:
                self._partial_counter += 1
                self._save_partial_scan()
                print("✓ Guardado parcial FINAL realizado")
            except Exception as e:
                print("⚠ Error guardando parcial final:", e)

    
    def on_scan_error(self, error_msg):
        """
        Manejar error de motor durante barrido
        """
        # Reanudar QTimer SIEMPRE tras error
        if not self.timer.isActive():
            self.timer.start(100)
            print("▶ Gráficos reanudados tras error")
        self.lbl_plot_status.setText("Estado plots: 🟢 ACTIVOS")
        self.lbl_plot_status.setStyleSheet("color: green; font-weight: bold;")
    
        # Restaurar estado de botones
        self.btn_abort_scan.setEnabled(False)
        self.btn_run_scan.setEnabled(True)
    
        # Limpiar referencia al worker
        self.worker = None
    
        self.lbl_scan_progress.setText(f"ERROR: {error_msg}")
        QMessageBox.critical(
            self,
            "Error de Motor",
            f"El barrido fue abortado debido a un error de motor:\n\n{error_msg}\n\n"
            "Posibles causas:\n"
            "- Motor desconectado\n"
            "- Obstrucción mecánica\n"
            "- Límite de carrera alcanzado\n"
            "- Fricción excesiva\n\n"
            "Verificar hardware antes de reintentar."
        )
        print(f"ERROR MOTOR: {error_msg}")
    
    def abort_scan(self):
        """
        Solicitar abortar el barrido actual de forma segura.
        El worker terminará el punto actual y luego se detendrá.
        """
        if hasattr(self, 'worker') and self.worker is not None and self.worker.isRunning():
            print("🛑 Usuario solicitó ABORTAR barrido")
            self.worker.abort()
            self.btn_abort_scan.setEnabled(False)  # Deshabilitar para evitar múltiples clicks
            self.lbl_scan_progress.setText("Abortando... terminando punto actual")
        else:
            print("⚠️  No hay barrido en curso para abortar")
    
    def on_scan_aborted(self):
        """
        Manejar cuando el barrido fue abortado por el usuario.
        Guarda los datos parciales en formato v1.0.0 con flag aborted=True.
        """
        try:
            # Reanudar QTimer SIEMPRE al abortar
            if not self.timer.isActive():
                self.timer.start(100)
                print("▶ Gráficos reanudados al finalizar barrido (abortado)")
            self.lbl_plot_status.setText("Estado plots: 🟢 ACTIVOS")
            self.lbl_plot_status.setStyleSheet("color: green; font-weight: bold;")
    
            # Restaurar estado de botones
            self.btn_abort_scan.setEnabled(False)
            self.btn_run_scan.setEnabled(True)
    
            # Limpiar referencia al worker
            self.worker = None
    
            # Guardar datos parciales si hay algo
            if len(self.scan_x) > 0:
                self._save_aborted_scan()
            else:
                self.lbl_scan_progress.setText("ABORTADO: sin datos")
                QMessageBox.information(self, "Barrido Abortado", "Barrido abortado antes de adquirir datos")
                print("⚠️ Barrido abortado sin datos")
        except Exception as e:
            error_msg = f"Error al guardar datos parciales: {e}"
            self.lbl_scan_progress.setText(error_msg)
            QMessageBox.critical(self, "Error", error_msg)
            print(error_msg)
            import traceback
            traceback.print_exc()
        # =====================================================
        # Guardado parcial FINAL forzado
        # =====================================================
        if self.enable_partial_saves:
            try:
                self._partial_counter += 1
                self._save_partial_scan()
                print("✓ Guardado parcial FINAL realizado")
            except Exception as e:
                print("⚠ Error guardando parcial final:", e)

    # ════════════════════════════════════════════════════════════════
    # NUEVO v1.0.0: FUNCIONES DE GUARDADO FORMATO ESTANDARIZADO
    # ════════════════════════════════════════════════════════════════
    
    def _prepare_scan_data(self):
        """
        Preparar datos de barrido en formato compatible con oct_data_saver.
        
        Convierte scan_win_opd de (N, MAX_WINDOWS, PEAKS_PER_WINDOW) 
        a formato requerido por saver: lista de (N,) donde cada elemento
        es una lista de MAX_WINDOWS arrays de picos.
        """
        # Convertir scan_win_opd al formato esperado por el saver
        win_opd_formatted = []
        
        for point_idx in range(len(self.scan_x)):
            point_windows = []
            
            for w in range(MAX_WINDOWS):
                # Extraer picos de esta ventana para este punto
                if point_idx < len(self.scan_win_opd):
                    peaks = self.scan_win_opd[point_idx][w]
                    # Filtrar NaN
                    valid_peaks = peaks[~np.isnan(peaks)]
                    point_windows.append(valid_peaks)
                else:
                    point_windows.append(np.array([]))
            
            win_opd_formatted.append(point_windows)
        
        return {
            'x': self.scan_x,
            'y': self.scan_y,
            'z': self.scan_z,
            'spectra': self.scan_spectra,
            'win_opd': win_opd_formatted,
        }
    
    def _prepare_metadata(self):
        """Preparar metadata del barrido"""
        # Determinar tipo de barrido
        scan_type = self._get_scan_type()
        
        # Determinar modo FFT
        fft_mode = 'CZT' if self.chk_czt_windows.isChecked() else 'FFT'
        
        return {
            'exposure_ms': self.spin_exp.value() if hasattr(self, 'spin_exp') else 10.0,
            'averages': 1,
            'fft_mode': fft_mode,
            'zero_padding': 0,
            'n_windows': len(self._active_windows),
            'scan_type': scan_type,
            'n_points_total': self._n_points_total,
            'start_time': self._start_time,
            'end_time': datetime.now(),
        }
    
    def _get_scan_type(self):
        """Detectar tipo de barrido basado en ejes usados"""
        use_x = self.chk_scan_x.isChecked()
        use_y = self.chk_scan_y.isChecked()
        use_z = self.chk_scan_z.isChecked()
        
        n_axes = sum([use_x, use_y, use_z])
        
        if n_axes == 1:
            return '1D'
        elif n_axes == 2:
            return '2D'
        elif n_axes == 3:
            return '3D'
        else:
            return 'unknown'
    
    def _save_partial_scan(self):
        """
        Guardar parcial acumulativo usando formato v1.0.0
        """
        scan_data = self._prepare_scan_data()
        metadata = self._prepare_metadata()
        
        # Generar filepath para parcial
        n_partials_total = int(1.0 / self.partial_save_interval)
        filepath = generate_filename(
            is_partial=True,
            part_index=self._partial_counter,
            parts_total=n_partials_total
        )
        
        # Guardar
        self.saver.save_scan(
            scan_data, 
            metadata, 
            filepath,
            is_partial=True,
            part_index=self._partial_counter,
            parts_total=n_partials_total
        )
        
        print(f"  └─ Archivo: {os.path.basename(filepath)}")
    
    def _save_final_scan(self):
        """
        Guardar barrido final usando formato v1.0.0
        """
        scan_data = self._prepare_scan_data()
        metadata = self._prepare_metadata()
        
        # Generar filepath para final
        filepath = generate_filename(is_partial=False)
        
        # Guardar
        self.saver.save_scan(
            scan_data, 
            metadata, 
            filepath,
            is_partial=False
        )
        
        # Mensaje de éxito
        fname = os.path.basename(filepath)
        msg = (
            f"✓ Barrido completado!\n\n"
            f"Puntos: {len(self.scan_x)}/{self._n_points_total}\n"
            f"Tipo: {metadata['scan_type']}\n"
            f"Modo: {metadata['fft_mode']}\n"
            f"Ventanas: {metadata['n_windows']}\n\n"
            f"Guardado en:\n{filepath}\n\n"
            f"Formato: v{self.saver.schema_version}"
        )
        
        if self.enable_partial_saves:
            msg += f"\n\nGuardados parciales: {self._partial_counter}"
        
        self.lbl_scan_progress.setText(f"✓ Guardado: {fname}")
        QMessageBox.information(self, "Éxito", msg)
        print(f"\n{'='*60}")
        print(f"✓ BARRIDO COMPLETADO")
        print(f"{'='*60}")
        print(f"Archivo: {filepath}")
        print(f"Puntos: {len(self.scan_x)}")
        print(f"Formato: v{self.saver.schema_version}")
        print(f"{'='*60}\n")
    
    def _save_aborted_scan(self):
        """
        Guardar barrido abortado usando formato v1.0.0
        Marca con IS_FINAL=False y PART_INDEX especial
        """
        scan_data = self._prepare_scan_data()
        metadata = self._prepare_metadata()
        
        # Generar filepath para abortado
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filepath = os.path.join(
            "Barridos Guardados",
            f"scan_{timestamp}_ABORTADO.npz"
        )
        
        # Asegurar que directorio existe
        os.makedirs("Barridos Guardados", exist_ok=True)
        
        # Guardar como parcial con índice 0 (indica abortado)
        self.saver.save_scan(
            scan_data, 
            metadata, 
            filepath,
            is_partial=True,
            part_index=0,
            parts_total=1
        )
        
        # Mensaje
        fname = os.path.basename(filepath)
        msg = (
            f"⚠️  Barrido ABORTADO\n\n"
            f"Puntos adquiridos: {len(self.scan_x)}/{self._n_points_total}\n"
            f"Completado: {len(self.scan_x)/self._n_points_total*100:.1f}%\n\n"
            f"Datos parciales guardados en:\n{filepath}\n\n"
            f"Formato: v{self.saver.schema_version}\n"
            f"Los datos son válidos y pueden analizarse."
        )
        
        self.lbl_scan_progress.setText(f"⚠️ ABORTADO: {fname}")
        QMessageBox.warning(self, "Barrido Abortado", msg)
        print(f"\n{'='*60}")
        print(f"⚠️  BARRIDO ABORTADO")
        print(f"{'='*60}")
        print(f"Archivo: {filepath}")
        print(f"Puntos: {len(self.scan_x)}/{self._n_points_total}")
        print(f"Formato: v{self.saver.schema_version}")
        print(f"{'='*60}\n")

    def closeEvent(self, event):
        """Manejar cierre de ventana"""
        self.timer.stop()
        
        if self.mot:
            try:
                self.mot.close()
            except:
                pass
        
        event.accept()
