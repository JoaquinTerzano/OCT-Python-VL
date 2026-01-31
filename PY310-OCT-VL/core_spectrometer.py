# -*- coding: utf-8 -*-
"""
Created on Fri Dec 19 22:12:30 2025
Updated: Jan 24 2026 - Renombrado gamma correction

@author: Lucas
"""

# =============================================================
# core_spectrometer.py
# Módulo de control HR4000 - lectura, seteo, guardado
# VERSIÓN REFACTORIZADA con gamma correction
# =============================================================

import numpy as np
from seabreeze.spectrometers import Spectrometer
import csv
import datetime

class HRSpectrometer:
    def __init__(self):
        self.spec = None
        self.dark_enabled = False
        # CORREGIDO P3: Renombrado de lin_enabled a gamma_correction
        self.gamma_correction = 1.0  # 1.0 = sin corrección, 0.5 = sqrt, 2.0 = cuadrado

    # ------------------------------------------
    # Inicializar espectrómetro
    # ------------------------------------------
    def connect(self):
        if self.spec is None:
            self.spec = Spectrometer.from_first_available()
        return self.spec is not None

    # ------------------------------------------
    # Set tiempo de integración (ms -> us)
    # ------------------------------------------
    def set_exposure_ms(self, t_ms: float):
        if self.spec is None:
            return
        t_us = int(t_ms * 1000)
        self.spec.integration_time_micros(t_us)

    # ------------------------------------------
    # CORREGIDO P3: Set gamma correction
    # ------------------------------------------
    def set_gamma_correction(self, gamma: float):
        """
        Configurar corrección gamma.
        
        Gamma < 1.0: Comprime altos (ej: 0.5 = sqrt, reduce saturación)
        Gamma = 1.0: Sin corrección (lineal)
        Gamma > 1.0: Expande bajos (ej: 2.0 = cuadrado, aumenta contraste)
        
        Típico para espectrómetros: 0.45 - 0.55 (compresión leve)
        """
        self.gamma_correction = max(0.1, min(3.0, gamma))  # Límites seguros

    # ------------------------------------------
    # Leer datos
    # ------------------------------------------
    def read(self):
        if self.spec is None:
            return None, None
        wl = self.spec.wavelengths()
        intens = self.spec.intensities()

        # Corrección 1: Dark substraction
        if self.dark_enabled:
            intens = intens - np.min(intens)

        # CORREGIDO P3: Gamma correction (antes "linearity")
        if self.gamma_correction != 1.0:
            # Asegurar valores no negativos antes de power
            intens = np.maximum(intens, 0)
            intens = np.power(intens, self.gamma_correction)

        return wl, intens

    # ------------------------------------------
    # Guardar CSV
    # ------------------------------------------
    def save_csv(self, wl, intens):
        now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"spec_{now}.csv"

        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Wavelength (nm)", "Intensity"])
            for x, y in zip(wl, intens):
                writer.writerow([float(x), float(y)])

        return filename
    
    # ------------------------------------------
    # LEGACY: Compatibilidad con código viejo
    # ------------------------------------------
    @property
    def lin_enabled(self):
        """DEPRECADO: Usar gamma_correction en su lugar"""
        return self.gamma_correction != 1.0
    
    @lin_enabled.setter
    def lin_enabled(self, value):
        """DEPRECADO: Usar set_gamma_correction() en su lugar"""
        self.gamma_correction = 0.5 if value else 1.0
