#!/usr/bin/env python3
"""
AI Processing untuk dataset e-nose kopi.

Fungsi utama:
1. Memuat data dari file CSV maupun TXT JSON
2. Mengekstraksi fitur statistik per siklus (mean + max setiap sensor)
3. Melatih model Random Forest untuk klasifikasi roasting
   (light / medium / dark)
4. Menyimpan model dan hasil prediksi ke file output

Contoh penggunaan:
    python scripts/5_ai_process_data.py --mode train
    python scripts/5_ai_process_data.py --mode predict --input data/light_20260810_160508.csv
    python scripts/5_ai_process_data.py --mode full
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import pickle
from pathlib import Path
from typing import Iterable, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split


ADC_COLS = [
    "adc_mq135",
    "adc_mq136",
    "adc_mq137",
    "adc_mq138",
    "adc_mq2",
    "adc_mq3",
    "adc_tgs822",
    "adc_tgs2620",
]

LABELS = ["light", "medium", "dark"]


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def list_data_files(data_dir: str | Path) -> List[Path]:
    root = Path(data_dir)
    if not root.exists():
        raise FileNotFoundError(f"Folder data tidak ditemukan: {root}")

    files = sorted(root.glob("*.csv")) + sorted(root.glob("*.txt"))
    files = [f for f in files if f.is_file()]
    return files


def normalize_label(value: object) -> str:
    if value is None:
        return "unknown"
    label = str(value).strip().lower()
    if label not in LABELS:
        return "unknown"
    return label


def extract_features_from_text_file(file_path: Path) -> pd.DataFrame:
    """Ekstrak fitur dari file txt JSON per status roasting."""
    rows = []
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            status = normalize_label(data.get("status"))
            if status == "unknown":
                continue

            row = {"source_file": file_path.name, "label": status}
            for col in ADC_COLS:
                value = data.get(col)
                row[col] = value
            rows.append(row)

    if not rows:
        return pd.DataFrame(columns=["source_file", "label", *ADC_COLS])

    df = pd.DataFrame(rows)
    for col in ADC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def extract_features_from_csv_file(file_path: Path) -> pd.DataFrame:
    """Ekstrak fitur dari CSV dengan kolom raw ADC + label + phase/cycle."""
    try:
        df = pd.read_csv(file_path)
    except Exception:
        return pd.DataFrame(columns=["source_file", "label", "cycle", *ADC_COLS])

    if "label" not in df.columns:
        return pd.DataFrame(columns=["source_file", "label", "cycle", *ADC_COLS])

    df = df.copy()
    df["label"] = df["label"].map(normalize_label)
    df = df[df["label"] != "unknown"].copy()

    if df.empty:
        return pd.DataFrame(columns=["source_file", "label", "cycle", *ADC_COLS])

    if "cycle" not in df.columns:
        df["cycle"] = 1

    df["source_file"] = file_path.name

    for col in ADC_COLS:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df


def aggregate_cycle_features(df: pd.DataFrame) -> pd.DataFrame:
    """Mengubah data raw sensor menjadi satu feature per siklus."""
    if df.empty:
        return pd.DataFrame(columns=["source_file", "label", "cycle", "n_samples"])

    group_cols = [col for col in ["source_file", "label", "cycle"] if col in df.columns]
    if not group_cols:
        df["source_file"] = "unknown"
        df["label"] = "unknown"
        df["cycle"] = 1
        group_cols = ["source_file", "label", "cycle"]

    rows = []
    for keys, group in df.groupby(group_cols, dropna=False):
        labels = keys if isinstance(keys, tuple) else (keys,)
        key_map = dict(zip(group_cols, labels))
        row = {
            "source_file": key_map.get("source_file", "unknown"),
            "label": key_map.get("label", "unknown"),
            "cycle": key_map.get("cycle", 1),
            "n_samples": len(group),
        }

        for col in ADC_COLS:
            vals = group[col].values.astype(float)
            if len(vals) == 0:
                row[f"mean_{col}"] = 0.0
                row[f"max_{col}"] = 0.0
            else:
                row[f"mean_{col}"] = float(np.mean(vals))
                row[f"max_{col}"] = float(np.max(vals))

        rows.append(row)

    out = pd.DataFrame(rows)
    return out


def load_feature_dataset(data_dir: str | Path) -> pd.DataFrame:
    """Load semua data dan hasilkan dataset fitur siap training/prediksi."""
    data_root = Path(data_dir)
    all_frames: List[pd.DataFrame] = []

    for file_path in list_data_files(data_root):
        if file_path.name.startswith("dataset_fitur"):
            continue

        if file_path.suffix.lower() == ".csv":
            raw = extract_features_from_csv_file(file_path)
        else:
            raw = extract_features_from_text_file(file_path)

        if raw.empty:
            continue
        features = aggregate_cycle_features(raw)
        if not features.empty:
            all_frames.append(features)

    if not all_frames:
        raise ValueError(f"Tidak ada data valid yang ditemukan di folder {data_root}")

    dataset = pd.concat(all_frames, ignore_index=True)
    dataset = dataset[dataset["label"] != "unknown"].copy()
    dataset.reset_index(drop=True, inplace=True)
    return dataset


def build_feature_columns() -> List[str]:
    cols = []
    for sensor in ADC_COLS:
        cols.extend([f"mean_{sensor}", f"max_{sensor}"])
    return cols


def train_model(dataset: pd.DataFrame, output_dir: str | Path) -> tuple[RandomForestClassifier, List[str], pd.DataFrame]:
    feature_cols = build_feature_columns()
    missing = [c for c in feature_cols if c not in dataset.columns]
    if missing:
        raise ValueError(f"Kolom fitur tidak lengkap. Kolom yang hilang: {missing}")

    X = dataset[feature_cols].to_numpy(dtype=float)
    y = dataset["label"].to_numpy()

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        stratify=y,
        random_state=42,
    )

    clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        class_weight="balanced",
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print("\nHasil evaluasi model:")
    print(f"Akurasi: {acc * 100:.2f}%")
    print(classification_report(y_test, y_pred, zero_division=0))
    print("Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred, labels=LABELS))

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    model_path = output_path / "coffee_roast_model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(clf, f)
    print(f"Model disimpan ke: {model_path}")

    dataset_path = output_path / "dataset_fitur_ai.csv"
    dataset.to_csv(dataset_path, index=False)
    print(f"Dataset fitur disimpan ke: {dataset_path}")

    return clf, feature_cols, dataset


def predict_with_model(model_path: str | Path, input_data: str | Path) -> pd.DataFrame:
    with open(model_path, "rb") as f:
        model = pickle.load(f)

    data_root = Path(input_data)
    if data_root.is_dir():
        dataset = load_feature_dataset(data_root)
    else:
        if data_root.suffix.lower() == ".csv":
            raw = extract_features_from_csv_file(data_root)
        else:
            raw = extract_features_from_text_file(data_root)
        if raw.empty:
            raise ValueError(f"File input tidak berisi data valid: {data_root}")
        dataset = aggregate_cycle_features(raw)

    feature_cols = build_feature_columns()
    X = dataset[feature_cols].to_numpy(dtype=float)
    preds = model.predict(X)

    result = dataset.copy()
    result["prediction"] = preds
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Processing dataset e-nose kopi")
    parser.add_argument("--mode", choices=["train", "predict", "full"], default="full")
    parser.add_argument("--data-dir", default="data", help="Folder data yang berisi CSV/TXT")
    parser.add_argument("--model-path", default="data/coffee_roast_model.pkl", help="Path file model")
    parser.add_argument("--input", default="", help="File atau folder input untuk prediksi")
    parser.add_argument("--output-dir", default="data", help="Folder output model/dataset")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parent.parent
    data_dir = (root / args.data_dir).resolve()
    output_dir = (root / args.output_dir).resolve()

    if args.mode in ["train", "full"]:
        dataset = load_feature_dataset(data_dir)
        model, _, _ = train_model(dataset, output_dir)
        print(f"\nModel siap dipakai: {output_dir / 'coffee_roast_model.pkl'}")

    if args.mode in ["predict", "full"]:
        if args.input:
            input_path = (root / args.input).resolve()
        else:
            input_path = data_dir

        if not input_path.exists():
            raise FileNotFoundError(f"Input tidak ditemukan: {input_path}")

        result = predict_with_model(output_dir / "coffee_roast_model.pkl", input_path)
        print("\nHasil prediksi:")
        print(result[["source_file", "label", "cycle", "prediction"]].head(20).to_string(index=False))


if __name__ == "__main__":
    main()
