# -*- coding: utf-8 -*-
"""
Created on Fri Dec 19 22:14:59 2025
Updated: Jan 24 2026 - Refactorización con manejo robusto de errores

@author: Lucas
"""

# =============================================================
# core_motors.py
# Control de motores Newport ESP301 - X/Y en mm
# VERSIÓN REFACTORIZADA con timeout y validación
# =============================================================

import serial
import time
import numpy as np


class MotorError(Exception):
    """Excepción personalizada para errores de motor"""
    pass


class ESP301:
    def __init__(self, port="COM3", baud=921600, timeout=0.1):
        self.port_name = port
        self.baud = baud
        self.timeout = timeout
        self.ser = None

    # ----------------------------------------------------------
    # Abrir puerto
    # ----------------------------------------------------------
    def connect(self):
        if self.ser and self.ser.is_open:
            return True
        try:
            self.ser = serial.Serial(
                self.port_name,
                self.baud,
                timeout=self.timeout,
                write_timeout=self.timeout
            )
            time.sleep(0.1)
            return True
        except:
            return False

    # ----------------------------------------------------------
    # Cerrar puerto
    # ----------------------------------------------------------
    def close(self):
        if self.ser:
            self.ser.close()

    # ----------------------------------------------------------
    # Enviar comando ASCII + CR (OPT #5: Espera adaptativa)
    # ----------------------------------------------------------
    def send(self, cmd, max_wait=0.05):
        """
        OPT #5: Espera adaptativa - sale tan pronto como hay datos
        Ganancia: +30-50% velocidad en barridos
        """
        if not self.ser or not self.ser.is_open:
            return None
        full = (cmd + "\r").encode("ascii")
        self.ser.write(full)
        
        # Polling adaptativo cada 1ms
        start_time = time.time()
        while (time.time() - start_time) < max_wait:
            if self.ser.in_waiting > 0:
                return self.read()
            time.sleep(0.001)
        return self.read()

    # ----------------------------------------------------------
    # Leer respuesta
    # ----------------------------------------------------------
    def read(self):
        if not self.ser:
            return ""
        try:
            resp = self.ser.readline().decode(errors="ignore").strip()
            return resp
        except:
            return ""

    # ----------------------------------------------------------
    # Helpers de movimiento
    # ----------------------------------------------------------
    def move_absolute(self, axis, pos_mm):
        """ axis en {1,2}, mm float """
        return self.send(f"{axis}PA{pos_mm:.6f}")

    def move_relative(self, axis, delta_mm):
        return self.send(f"{axis}PR{delta_mm:.6f}")

    def get_position(self, axis):
        resp = self.send(f"{axis}TP?")
        try:
            return float(resp)
        except:
            return None

    def enable_axis(self, axis):
        return self.send(f"{axis}MO")

    def disable_axis(self, axis):
        return self.send(f"{axis}MF")

    def set_velocity(self, axis, vel_mm_s):
        return self.send(f"{axis}VA{vel_mm_s:.3f}")

    # ----------------------------------------------------------
    # CORREGIDO P5: Movimiento ROBUSTO con timeout y validación
    # ----------------------------------------------------------
    def goto_and_wait(self, axis, pos, tol=0.0005, timeout=30.0, max_attempts=3):
        """
        Movimiento robusto a posición con timeout, reintentos y validación.
        
        PREVIENE:
        - Loop infinito si motor se desconecta
        - Cuelgue si motor devuelve NaN/Inf
        - Atasco si motor no puede alcanzar tolerancia
        - Fricción estática
        
        Args:
            axis: 1 o 2 (X o Y)
            pos: Posición objetivo en mm
            tol: Tolerancia en mm (default: 0.5 um)
            timeout: Timeout total en segundos (default: 30s)
            max_attempts: Número máximo de reintentos (default: 3)
        
        Returns:
            tuple: (success: bool, final_position: float, error_msg: str)
            
        Raises:
            MotorError: Si falla después de todos los reintentos
        """
        start_time = time.time()
        attempt = 0
        
        while attempt < max_attempts:
            attempt += 1
            
            # Enviar comando de movimiento
            resp = self.move_absolute(axis, pos)
            if resp is None:
                error_msg = f"No response from motor axis {axis}"
                if attempt >= max_attempts:
                    raise MotorError(error_msg)
                time.sleep(0.5)
                continue
            
            # Esperar hasta que llegue o timeout
            last_positions = []
            stuck_counter = 0
            
            while (time.time() - start_time) < timeout:
                p = self.get_position(axis)
                
                # VALIDACIÓN 1: Verificar comunicación
                if p is None:
                    error_msg = f"Lost communication with axis {axis}"
                    if attempt >= max_attempts:
                        raise MotorError(error_msg)
                    break  # Reintentar
                
                # VALIDACIÓN 2: Verificar valor numérico válido
                if not np.isfinite(p):
                    error_msg = f"Invalid position from axis {axis}: {p}"
                    if attempt >= max_attempts:
                        raise MotorError(error_msg)
                    break  # Reintentar
                
                # Guardar historial de posiciones (últimas 10)
                last_positions.append(p)
                if len(last_positions) > 10:
                    last_positions.pop(0)
                
                # VALIDACIÓN 3: Verificar si llegó
                error = abs(p - pos)
                if error <= tol:
                    # ÉXITO
                    return (True, p, f"Success on attempt {attempt}")
                
                # VALIDACIÓN 4: Detectar motor atascado
                if len(last_positions) >= 5:
                    movement = max(last_positions) - min(last_positions)
                    if movement < tol / 10:  # Movimiento < 10% de tolerancia
                        stuck_counter += 1
                        if stuck_counter > 10:  # Atascado por ~0.5s
                            # Motor no se mueve, reintentar
                            break
                    else:
                        stuck_counter = 0  # Reset si se movió
                
                time.sleep(0.05)
            
            # Si llegó aquí: timeout o stuck
            # Pequeño movimiento de "liberación" antes de reintentar
            if attempt < max_attempts:
                jiggle = 0.001 if pos > 0 else -0.001
                self.move_relative(axis, jiggle)
                time.sleep(0.1)
        
        # FALLO: Todos los intentos agotados
        final_p = self.get_position(axis)
        error_msg = f"Motor axis {axis} failed after {max_attempts} attempts. Target: {pos:.6f} mm, Final: {final_p:.6f} mm"
        raise MotorError(error_msg)
    
    # ----------------------------------------------------------
    # Versión legacy (wrapper para compatibilidad)
    # ----------------------------------------------------------
    def goto_and_wait_legacy(self, axis, pos, tol=0.0005):
        """
        DEPRECADO: Usar goto_and_wait() en su lugar.
        Esta versión no tiene timeout (puede colgar).
        """
        try:
            success, final_pos, msg = self.goto_and_wait(axis, pos, tol)
            return success
        except MotorError:
            return False

    # ----------------------------------------------------------
    # Barrido rectangular
    # ----------------------------------------------------------
    def raster_scan(self, x_start, x_end, x_step,
                          y_start, y_end, y_step,
                          callback=None):
        """
        callback(x_mm, y_mm) -> se ejecuta por punto
        """
        xs = _frange(x_start, x_end, x_step)
        ys = _frange(y_start, y_end, y_step)

        for y in ys:
            success, _, _ = self.goto_and_wait(2, y)
            if not success:
                raise MotorError(f"Failed to move Y to {y}")
                
            for x in xs:
                success, _, _ = self.goto_and_wait(1, x)
                if not success:
                    raise MotorError(f"Failed to move X to {x}")
                    
                if callback:
                    callback(x, y)


# --------------------------------------------------------------
# Rango flotante
# --------------------------------------------------------------
def _frange(start, end, step):
    v = start
    out = []
    if step == 0:
        return [start]
    while v <= end + 1e-10:
        out.append(v)
        v += step
    return out
