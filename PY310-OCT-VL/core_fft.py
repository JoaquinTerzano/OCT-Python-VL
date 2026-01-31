# -*- coding: utf-8 -*-
"""
Created on Fri Dec 19 22:13:21 2025
Modified: Jan 23 2026 - Mejoras en CZT y detección de picos

@author: Lucas
"""

# =============================================================
# core_fft.py - MEJORADO
# CZT tipo MATLAB + filtros + picos adaptativos
# =============================================================

import numpy as np
from scipy.signal import find_peaks


# -------------------------------------------------------------
# CZT equivalente EXACTO a fftZ.m de MATLAB
# -------------------------------------------------------------
def czt_zoom(signal, f1, f2, fs, m):
    """
    Chirp Z-Transform (CZT) - Implementación equivalente a MATLAB
    
    Parámetros:
    -----------
    signal : array_like
        Señal de entrada
    f1 : float
        Frecuencia inicial (OPD mínima en metros)
    f2 : float
        Frecuencia final (OPD máxima en metros)
    fs : float
        Frecuencia de muestreo
    m : int
        Número de puntos de salida
    
    Retorna:
    --------
    z : ndarray
        Transformada CZT (compleja)
    fz : ndarray
        Eje de frecuencias correspondiente
    """
    x = np.asarray(signal, dtype=np.complex128)
    k = len(x)
    
    # Ajustar m a potencia de 2 más cercana (como MATLAB)
    pot0 = 2 ** int(np.ceil(np.log2(m)))
    pot1 = pot0 // 2
    m = pot1 if abs(m - pot1) < abs(m - pot0) else pot0
    
    # Parámetros CZT
    n = np.arange(k)
    
    # Punto de inicio en el círculo unitario
    A = np.exp(-1j * 2 * np.pi * f1 / fs)
    
    # Ratio de espiral (relacionado con el zoom)
    beta = (f2 - f1) / (m * fs)
    W = np.exp(1j * 2 * np.pi * beta)
    
    # Secuencia chirp para n
    nn2 = n * n / 2.0
    W_nn2 = W ** nn2
    
    # Pre-multiplicación de la señal
    y = x * (A ** (-n)) * W_nn2
    
    # Convolución vía FFT
    nfft = 2 ** int(np.ceil(np.log2(k + m - 1)))
    
    # FFT de la señal pre-multiplicada
    fy = np.fft.fft(y, nfft)
    
    # Construir kernel de convolución
    # Parte 1: W^(-n²/2) para n=0..m-1
    v_part1 = W ** (-(np.arange(m) ** 2) / 2.0)
    
    # Parte 2: zeros para rellenar
    v_part2 = np.zeros(nfft - k - m + 1)
    
    # Parte 3: W^(-n²/2) para n=(k-1)..1 (invertido)
    v_part3 = W ** (-(np.arange(k-1, 0, -1) ** 2) / 2.0)
    
    v = np.concatenate([v_part1, v_part2, v_part3])
    fv = np.fft.fft(v)
    
    # Convolución en dominio de frecuencia
    g = np.fft.ifft(fy * fv)[:m]
    
    # Post-multiplicación
    mm = np.arange(m)
    z = g * W ** (mm * mm / 2.0)
    
    # Eje de frecuencias de salida
    fz = f1 + (f2 - f1) * mm / m
    
    return z, fz


# -------------------------------------------------------------
# Aplicar filtro a espectro → chirp / CZT
# -------------------------------------------------------------
def apply_filter(xj, spec, f1, f2, npoints):
    """
    Aplicar CZT a espectro procesado
    
    Parámetros:
    -----------
    xj : array_like
        Eje espacial o de frecuencia
    spec : array_like
        Datos interpolados o correlados
    f1 : float
        OPD mínima (m)
    f2 : float
        OPD máxima (m)
    npoints : int
        Resolución de salida
    
    Retorna:
    --------
    fz : ndarray
        Eje de frecuencias (OPD)
    z : ndarray
        Transformada CZT
    """
    # Calcular frecuencia de muestreo del eje de entrada
    fs = abs(1.0 / np.mean(np.diff(xj)))
    
    # Aplicar CZT
    z, fz = czt_zoom(spec, f1, f2, fs, npoints)
    
    return fz, z


# -------------------------------------------------------------
# Detectar picos con umbral adaptativo (como MATLAB picos2)
# -------------------------------------------------------------
def detect_peaks(z, fz, nmax=5, threshold_ratio=0.3, min_width=3e-6):
    """
    Detecta picos con estrategia adaptativa como MATLAB
    
    Parámetros:
    -----------
    z : array_like
        Señal transformada (compleja)
    fz : array_like
        Eje de frecuencias (OPD en metros)
    nmax : int
        Cantidad máxima de picos a detectar
    threshold_ratio : float
        Umbral inicial como fracción del máximo (default: 0.3)
    min_width : float
        Ancho mínimo de pico en metros (default: 3e-6 = 3 µm)
    
    Retorna:
    --------
    locs : list
        Posiciones de picos (en metros)
    pks : list
        Alturas de picos
    idx : list
        Índices en el array
    """
    mag = np.abs(z)
    
    if len(mag) == 0:
        return [], [], []
    
    # Convertir min_width de metros a número de puntos
    if len(fz) > 1:
        df = np.mean(np.diff(fz))
        width_samples = max(1, int(min_width / abs(df)))
    else:
        width_samples = 1
    
    # INTENTO 1: Umbral alto (30% del máximo)
    umbral_alto = np.max(mag) * threshold_ratio
    
    try:
        peaks, props = find_peaks(
            mag,
            height=umbral_alto,
            prominence=umbral_alto * 0.5,
            width=width_samples
        )
    except:
        peaks = np.array([])
    
    # INTENTO 2: Si no encontró picos, reducir umbral (como MATLAB)
    if len(peaks) == 0:
        umbral_bajo = np.max(mag) * 0.1  # 10% del máximo
        
        try:
            peaks, props = find_peaks(
                mag,
                prominence=umbral_bajo * 0.5,
                width=max(1, width_samples // 2)  # Reducir ancho mínimo también
            )
        except:
            peaks = np.array([])
    
    # Si aún no hay picos, buscar solo por altura mínima
    if len(peaks) == 0:
        umbral_minimo = np.max(mag) * 0.05
        try:
            peaks, props = find_peaks(mag, height=umbral_minimo)
        except:
            return [], [], []
    
    # Ordenar por altura (descendente) y limitar cantidad
    if len(peaks) > 0:
        heights = mag[peaks]
        order = np.argsort(heights)[::-1]
        peaks = peaks[order][:nmax]
        
        # Extraer posiciones y alturas
        locs = fz[peaks]
        pks = mag[peaks]
        
        return locs.tolist(), pks.tolist(), peaks.tolist()
    
    return [], [], []


# -------------------------------------------------------------
# Detectar picos en ventana específica (para GUI)
# -------------------------------------------------------------
def detect_peaks_in_window(z, fz, f_min, f_max, nmax=5, min_width=3e-6):
    """
    Detecta picos solo en una ventana de frecuencias específica
    
    Parámetros:
    -----------
    z : array_like
        Señal transformada
    fz : array_like
        Eje de frecuencias (metros)
    f_min : float
        OPD mínima de la ventana (metros)
    f_max : float
        OPD máxima de la ventana (metros)
    nmax : int
        Número máximo de picos
    min_width : float
        Ancho mínimo en metros
    
    Retorna:
    --------
    locs : list
        Posiciones dentro de la ventana
    pks : list
        Alturas
    idx : list
        Índices globales
    """
    # Máscara para la ventana
    mask = (fz >= f_min) & (fz <= f_max)
    
    if not np.any(mask):
        return [], [], []
    
    # Extraer datos de la ventana
    z_window = z[mask]
    fz_window = fz[mask]
    
    # Detectar picos en la ventana
    locs, pks, idx_local = detect_peaks(
        z_window, 
        fz_window, 
        nmax=nmax,
        min_width=min_width
    )
    
    # Convertir índices locales a globales
    indices_globales = np.where(mask)[0]
    idx_global = [indices_globales[i] for i in idx_local]
    
    return locs, pks, idx_global


# -------------------------------------------------------------
# Función auxiliar: Calcular resolución esperada
# -------------------------------------------------------------
def calculate_resolution(wl_min, wl_max):
    """
    Calcula la resolución teórica del OCT
    
    Parámetros:
    -----------
    wl_min : float
        Longitud de onda mínima (nm)
    wl_max : float
        Longitud de onda máxima (nm)
    
    Retorna:
    --------
    resolution : float
        Resolución en micrómetros
    """
    wl_min_m = wl_min * 1e-9
    wl_max_m = wl_max * 1e-9
    wl_center = (wl_min_m + wl_max_m) / 2
    
    # Resolución axial (FWHM)
    resolution = (2 * np.log(2) / np.pi) * (wl_center ** 2) / (wl_max_m - wl_min_m)
    
    return resolution * 1e6  # Convertir a µm


# -------------------------------------------------------------
# Función auxiliar: Calcular rango de profundidad
# -------------------------------------------------------------
def calculate_depth_range(wl_min, wl_max, n_pixels):
    """
    Calcula el rango de profundidad máximo alcanzable
    
    Parámetros:
    -----------
    wl_min : float
        Longitud de onda mínima (nm)
    wl_max : float
        Longitud de onda máxima (nm)
    n_pixels : int
        Número de píxeles del detector
    
    Retorna:
    --------
    max_depth : float
        Profundidad máxima en milímetros
    """
    wl_min_m = wl_min * 1e-9
    wl_max_m = wl_max * 1e-9
    
    # Diferencia en número de onda
    k_max = 2 * np.pi / wl_min_m
    k_min = 2 * np.pi / wl_max_m
    dk = (k_max - k_min) / n_pixels
    
    # Profundidad máxima
    max_depth = np.pi / dk
    
    return max_depth * 1e3  # Convertir a mm


# -------------------------------------------------------------
# Función de prueba
# -------------------------------------------------------------
def test_czt():
    """Función de prueba para verificar CZT"""
    # Crear señal de prueba
    fs = 1000  # Hz
    t = np.linspace(0, 1, fs)
    signal = np.sin(2 * np.pi * 50 * t) + 0.5 * np.sin(2 * np.pi * 120 * t)
    
    # Aplicar CZT
    f1 = 0
    f2 = 200  # Hz
    m = 512
    
    z, fz = czt_zoom(signal, f1, f2, fs, m)
    
    # Detectar picos
    locs, pks, idx = detect_peaks(z, fz, nmax=3)
    
    print("Test CZT:")
    print(f"  Señal: {len(signal)} puntos")
    print(f"  CZT: {len(z)} puntos")
    print(f"  Picos detectados: {len(locs)}")
    for i, (loc, pk) in enumerate(zip(locs, pks)):
        print(f"    Pico {i+1}: {loc:.1f} Hz, amplitud {pk:.2f}")
    
    return z, fz, locs, pks


if __name__ == "__main__":
    # Ejecutar prueba
    test_czt()
    
    # Calcular parámetros teóricos para OCT típico
    print("\nParámetros teóricos OCT (780-920 nm):")
    res = calculate_resolution(780, 920)
    depth = calculate_depth_range(780, 920, 3648)
    print(f"  Resolución teórica: {res:.2f} µm")
    print(f"  Profundidad máxima: {depth:.2f} mm")
