"""
data_loader.py
--------------
Membaca file .txt hasil pembacaan sensor e-nose (8 channel) yang disusun
dalam folder per kelas, sesuai struktur dataset dari jurnal MDPI Sensors
10(1):36 (AQ_Coffee, HQ_Coffee, LQ_Coffee).

Format file .txt yang didukung:
  1) Header 8 baris nama sensor, diikuti 1/lebih baris angka pembacaan, ATAU
  2) File hanya berisi baris-baris angka (time-series 8 kolom).

Target klasifikasi di pipeline ini adalah KUALITAS / CACAT MUTU kopi
(Adulterated Quality / High Quality / Low Quality), sesuai label asli yang
dipakai di dataset jurnal tersebut -- BUKAN tingkat roasting.
"""

import os
import numpy as np

# Urutan & nama 8 sensor sesuai spesifikasi yang diberikan
SENSOR_NAMES = [
    "SP12A_FlammableGases",
    "SP31_OrganicSolvents",
    "TGS813_CombustibleGas",
    "TGS842_MethaneNaturalGas",
    "SPAQ3_AirQualityControl",
    "TGS823_CombustibleGases",
    "ST31_OrganicSolvents",
    "TGS800",
]

# Label kualitas/cacat mutu asli dari dataset jurnal -- ini yang dipakai
# sebagai target klasifikasi Random Forest.
QUALITY_LABEL_MAP = {
    "AQ_Coffee": "Adulterated_Quality",
    "HQ_Coffee": "High_Quality",
    "LQ_Coffee": "Low_Quality",
}


def _parse_txt_file(filepath):
    """
    Parse satu file txt e-nose menjadi array shape (n_timesteps, 8).
    Baris non-numerik (nama sensor, keterangan channel) otomatis dilewati.
    """
    rows = []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            tokens = line.split()
            nums = []
            for t in tokens:
                try:
                    nums.append(float(t))
                except ValueError:
                    nums = []
                    break
            if len(nums) >= 8:
                # kalau ada kolom index/timestamp di depan, ambil 8 terakhir
                rows.append(nums[-8:])
    if not rows:
        raise ValueError(f"Tidak ada baris numerik 8-kolom yang valid di: {filepath}")
    return np.array(rows, dtype=float)


def load_dataset(data_dir, label_map=None):
    """
    Membaca seluruh file .txt di data_dir/<nama_folder_kelas>/*.txt

    Parameters
    ----------
    data_dir : str
        Path ke folder utama berisi AQ_Coffee/, HQ_Coffee/, LQ_Coffee/
    label_map : dict, optional
        Mapping {nama_folder: label_kelas}. Default: QUALITY_LABEL_MAP.

    Returns
    -------
    list of dict, tiap dict berisi:
        sample_id, source_folder, quality_label, readings (np.ndarray)
    """
    if label_map is None:
        label_map = QUALITY_LABEL_MAP

    records = []
    for folder_name, label in label_map.items():
        folder_path = os.path.join(data_dir, folder_name)
        if not os.path.isdir(folder_path):
            print(f"[WARNING] Folder tidak ditemukan, dilewati: {folder_path}")
            continue
        files = sorted(f for f in os.listdir(folder_path) if f.lower().endswith(".txt"))
        if not files:
            print(f"[WARNING] Tidak ada file .txt di: {folder_path}")
        for fname in files:
            fpath = os.path.join(folder_path, fname)
            try:
                readings = _parse_txt_file(fpath)
            except ValueError as e:
                print(f"[SKIP] {e}")
                continue
            records.append({
                "sample_id": fname,
                "source_folder": folder_name,
                "quality_label": label,
                "readings": readings,
            })

    if not records:
        raise RuntimeError(
            "Tidak ada data yang berhasil dibaca. Cek path data_dir dan isi foldernya."
        )
    print(f"[INFO] Berhasil membaca {len(records)} sampel dari {data_dir}")
    return records
