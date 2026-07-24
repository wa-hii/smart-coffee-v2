import os
import numpy as np

#  8 sensor sesuai spesifikasi yang diberikan
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

# label kualitas kopi sesuai dataset
QUALITY_LABEL_MAP = {
    "AQ_Coffee": "Adulterated_Quality",
    "HQ_Coffee": "High_Quality",
    "LQ_Coffee": "Low_Quality",
}


def _parse_txt_file(filepath):
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