
# -*- coding: utf-8 -*-
"""
Maneja el guardado de datos OCT en formato .npz unificado.

Uso:
    saver = OCTDataSaver()
    path  = generate_filename(is_partial=False)
    saver.save_scan(scan_data, metadata, path)
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List

import numpy as np

# === Constantes del formato (coinciden con lo que espera la GUI) ===
MAX_WINDOWS = 5
N_PEAKS_PER_WINDOW = 3


class OCTDataSaver:
    """
    Guardado de barridos OCT en formato .npz unificado.
    Compatible con la GUI que importa OCTDataSaver y accede a .schema_version
    """

    def __init__(self, instrument: str = "OCT-Python-HR4000", schema_version: str = "1.0.0") -> None:
        self.instrument = instrument
        self.schema_version = schema_version  # <- la GUI usa este atributo

    # ------------------------- helpers internos ------------------------- #
    def prepare_window_data(self, scan_win_opd: List[List[np.ndarray]], n_points: int) -> Dict[str, np.ndarray]:
        """
        Convierte una lista (N puntos) donde cada elemento es una lista de MAX_WINDOWS arrays de picos
        en 5 arrays (W1..W5) de shape (N,) dtype=object, con vectores de 3 picos (rellenados con NaN).
        """
        window_data: Dict[str, np.ndarray] = {}
        for w in range(MAX_WINDOWS):
            # Cada elemento (punto) es un vector de 3 picos (float) con NaN si faltan
            win_array = np.empty(n_points, dtype=object)
            for i in range(n_points):
                # picos "crudos" (puede ser tamaño 0..3) para punto i, ventana w
                if i < len(scan_win_opd) and w < len(scan_win_opd[i]):
                    peaks = np.asarray(scan_win_opd[i][w], dtype=float)
                else:
                    peaks = np.asarray([], dtype=float)

                fixed = np.full(N_PEAKS_PER_WINDOW, np.nan, dtype=float)
                n_avail = min(len(peaks), N_PEAKS_PER_WINDOW)
                if n_avail:
                    fixed[:n_avail] = peaks[:n_avail]
                win_array[i] = fixed

            window_data[f"W{w+1}"] = win_array
        return window_data

    # ------------------------------ API -------------------------------- #
    def save_scan(
        self,
        scan_data: Dict[str, Any],   # {'x','y','z','spectra','win_opd'}
        metadata: Dict[str, Any],    # {'exposure_ms','averages','fft_mode',...}
        filepath: str,
        is_partial: bool = False,
        part_index: int | None = None,
        parts_total: int | None = None,
    ) -> str:
        """
        Guarda barrido completo o parcial en formato .npz unificado.
        """
        # ------ Datos dependientes de N ------ #
        x = scan_data.get("x", [])
        y = scan_data.get("y", [])
        z = scan_data.get("z", [])
        n_points = len(x)

        X = np.asarray(x, dtype=np.float64)
        Y = np.asarray(y, dtype=np.float64)
        Z = np.asarray(z, dtype=np.float64)

        spectra = scan_data.get("spectra", [])
        if len(spectra) > 0:
            SPECTRUM = np.vstack(spectra).astype(np.float64)
        else:
            # ancho 3648 según HR4000 (ajustar si tu espectrómetro difiere)
            SPECTRUM = np.empty((0, 3648), dtype=np.float64)

        # Ventanas de picos en formato unificado
        window_data = self.prepare_window_data(scan_data.get("win_opd", []), n_points)

        # ------ Metadata (escalares) ------ #
        EXPOSURE_MS = np.float64(metadata.get("exposure_ms", 0))
        AVERAGES = np.int32(metadata.get("averages", 1))
        FFT_MODE = str(metadata.get("fft_mode", "FFT")).strip().upper()
        ZERO_PADDING = np.int32(metadata.get("zero_padding", 0))
        N_WINDOWS = np.int32(metadata.get("n_windows", 0))
        N_PEAKS_PER_WINDOW_META = np.int32(N_PEAKS_PER_WINDOW)

        SCAN_TYPE = str(metadata.get("scan_type", "unknown"))
        N_POINTS_TOTAL = np.int32(metadata.get("n_points_total", n_points))
        N_POINTS_ACQUIRED = np.int32(n_points)

        if is_partial:
            PART_INDEX = np.int32(part_index if part_index is not None else 0)
            PARTS_TOTAL = np.int32(parts_total if parts_total is not None else 1)
            IS_FINAL = np.bool_(False)
        else:
            PART_INDEX = np.int32(0)
            PARTS_TOTAL = np.int32(1)
            IS_FINAL = np.bool_(True)

        start_dt = metadata.get("start_time", datetime.now())
        end_dt = metadata.get("end_time", datetime.now())
        START_TIME = start_dt.isoformat()
        END_TIME = end_dt.isoformat()
        DURATION_SEC = np.float64((end_dt - start_dt).total_seconds())

        save_dict: Dict[str, Any] = {
            # Datos N-dependientes
            "X": X,
            "Y": Y,
            "Z": Z,
            "SPECTRUM": SPECTRUM,
            **window_data,  # W1..W5

            # Metadata de adquisición/procesamiento
            "EXPOSURE_MS": EXPOSURE_MS,
            "AVERAGES": AVERAGES,
            "FFT_MODE": FFT_MODE,
            "ZERO_PADDING": ZERO_PADDING,
            "N_WINDOWS": N_WINDOWS,
            "N_PEAKS_PER_WINDOW": N_PEAKS_PER_WINDOW_META,

            # Metadata del barrido
            "SCAN_TYPE": SCAN_TYPE,
            "N_POINTS_TOTAL": N_POINTS_TOTAL,
            "N_POINTS_ACQUIRED": N_POINTS_ACQUIRED,

            # Metadata de guardados parciales
            "PART_INDEX": PART_INDEX,
            "PARTS_TOTAL": PARTS_TOTAL,
            "IS_FINAL": IS_FINAL,

            # Metadata de tiempo y SW/HW
            "START_TIME": START_TIME,
            "END_TIME": END_TIME,
            "DURATION_SEC": DURATION_SEC,
            "INSTRUMENT": self.instrument,
            "SOFTWARE_VERSION": self.schema_version,
        }

        # Asegurar directorio destino
        out_dir = os.path.dirname(filepath) or "."
        os.makedirs(out_dir, exist_ok=True)

        np.savez(filepath, **save_dict)
        return filepath


# ------------------------- utilitarios de nombre ------------------------- #
def generate_filename(
    base_dir: str = "Barridos Guardados",
    is_partial: bool = False,
    part_index: int | None = None,
    parts_total: int | None = None,
) -> str:
    """
    Final:   scan_YYYY-MM-DD_HH-MM.npz
    Parcial: scan_YYYY-MM-DD_HH-MM_part_XXofYY.npz
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    if is_partial and part_index is not None and parts_total is not None:
        filename = f"scan_{timestamp}_part_{part_index:02d}of{parts_total:02d}.npz"
    else:
        filename = f"scan_{timestamp}.npz"

    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, filename)


# --------------------------- utilitarios de lectura --------------------------- #
def load_scan(filepath: str):
    """Carga un .npz y separa data/metadata en dicts útiles."""
    npz = np.load(filepath, allow_pickle=True)
    data = {k: npz[k] for k in ["X", "Y", "Z", "SPECTRUM", "W1", "W2", "W3", "W4", "W5"] if k in npz.files}

    metadata = {
        "EXPOSURE_MS": float(npz["EXPOSURE_MS"]),
        "AVERAGES": int(npz["AVERAGES"]),
        "FFT_MODE": str(npz["FFT_MODE"]),
        "ZERO_PADDING": int(npz["ZERO_PADDING"]),
        "N_WINDOWS": int(npz["N_WINDOWS"]),
        "N_PEAKS_PER_WINDOW": int(npz["N_PEAKS_PER_WINDOW"]),
        "SCAN_TYPE": str(npz["SCAN_TYPE"]),
        "N_POINTS_TOTAL": int(npz["N_POINTS_TOTAL"]),
        "N_POINTS_ACQUIRED": int(npz["N_POINTS_ACQUIRED"]),
        "PART_INDEX": int(npz["PART_INDEX"]),
        "PARTS_TOTAL": int(npz["PARTS_TOTAL"]),
        "IS_FINAL": bool(npz["IS_FINAL"]),
        "START_TIME": str(npz["START_TIME"]),
        "END_TIME": str(npz["END_TIME"]),
        "DURATION_SEC": float(npz["DURATION_SEC"]),
        "INSTRUMENT": str(npz["INSTRUMENT"]),
        "SOFTWARE_VERSION": str(npz["SOFTWARE_VERSION"]),
    }
    return data, metadata


def print_scan_info(filepath: str) -> None:
    """Imprime un resumen del archivo .npz para verificación rápida."""
    import os as _os

    data, meta = load_scan(filepath)
    print("=" * 60)
    print(f"Archivo: {_os.path.basename(filepath)}")
    print("=" * 60)
    print(f"Puntos: {meta['N_POINTS_ACQUIRED']}/{meta['N_POINTS_TOTAL']}")
    print(f"Tipo: {meta['SCAN_TYPE']}")
    print(f"Parcial: {'Sí' if not meta['IS_FINAL'] else 'No'}")
    if not meta["IS_FINAL"]:
        print(f"  Parte {meta['PART_INDEX']}/{meta['PARTS_TOTAL']}")
    print(f"\nExposición: {meta['EXPOSURE_MS']} ms")
    print(f"Ventanas activas: {meta['N_WINDOWS']}")
    print(f"Modo: {meta['FFT_MODE']}")
    print(f"\nInicio: {meta['START_TIME']}")
    print(f"Fin: {meta['END_TIME']}")
    print(f"Duración: {meta['DURATION_SEC']:.1f} s")
    print(f"\nInstrumento: {meta['INSTRUMENT']}")
    print(f"Versión SW (schema): {meta['SOFTWARE_VERSION']}")
    print("=" * 60)
    print("\nVentanas OPD (primeros 3 puntos):")
    for w_idx in range(min(MAX_WINDOWS, meta["N_WINDOWS"] if "N_WINDOWS" in meta else MAX_WINDOWS)):
        wkey = f"W{w_idx+1}"
        if wkey in data:
            print(f" {wkey}:")
            for i in range(min(3, len(data[wkey]))):
                print(f"   [{i}]: {data[wkey][i]}")