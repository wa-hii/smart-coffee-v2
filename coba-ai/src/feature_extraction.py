"""
feature_extraction.py
----------------------
Mengubah data mentah pembacaan sensor (per sampel, bisa berupa satu baris
angka atau time-series beberapa baris) menjadi fitur statistik siap latih
untuk Random Forest.

Fitur yang diekstrak per sensor: mean, std, max, min, range, slope (tren).
Kalau file cuma 1 baris pembacaan, std/slope otomatis 0 -- tetap valid.
"""

import numpy as np
import pandas as pd
from src.data_loader import SENSOR_NAMES


def extract_features(records):
    """
    Parameters
    ----------
    records : list of dict (hasil dari data_loader.load_dataset)

    Returns
    -------
    pd.DataFrame
        Satu baris per sampel, kolom fitur + metadata (sample_id,
        source_folder, roast_label)
    """
    rows = []
    for rec in records:
        readings = rec["readings"]  # shape (n_timesteps, 8)
        feat = {}
        for i, sensor in enumerate(SENSOR_NAMES):
            col = readings[:, i]
            feat[f"{sensor}_mean"] = float(np.mean(col))
            feat[f"{sensor}_std"] = float(np.std(col))
            feat[f"{sensor}_max"] = float(np.max(col))
            feat[f"{sensor}_min"] = float(np.min(col))
            feat[f"{sensor}_range"] = float(np.max(col) - np.min(col))
            if len(col) > 1:
                feat[f"{sensor}_slope"] = float(np.polyfit(np.arange(len(col)), col, 1)[0])
            else:
                feat[f"{sensor}_slope"] = 0.0

        feat["sample_id"] = rec["sample_id"]
        feat["source_folder"] = rec["source_folder"]
        feat["quality_label"] = rec["quality_label"]
        rows.append(feat)

    df = pd.DataFrame(rows)
    return df


def get_feature_columns(df):
    """Ambil daftar nama kolom fitur numerik saja (tanpa metadata)."""
    exclude = {"sample_id", "source_folder", "quality_label"}
    return [c for c in df.columns if c not in exclude]
