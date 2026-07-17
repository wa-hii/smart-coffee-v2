"""
predict.py
-----------
Memuat model Random Forest yang sudah dilatih & memprediksi kualitas/cacat
mutu kopi untuk 1 file pembacaan sensor baru (mis. hasil real-time dari
Raspberry Pi / ATmega2560 di alat RoastSense).
"""

import os
import joblib
import numpy as np

from src.data_loader import _parse_txt_file, SENSOR_NAMES


def _extract_features_single(readings):
    """Ekstraksi fitur untuk satu sampel (dipakai juga saat inference)."""
    feat = []
    for i in range(len(SENSOR_NAMES)):
        col = readings[:, i]
        feat.append(np.mean(col))
        feat.append(np.std(col))
        feat.append(np.max(col))
        feat.append(np.min(col))
        feat.append(np.max(col) - np.min(col))
        if len(col) > 1:
            feat.append(np.polyfit(np.arange(len(col)), col, 1)[0])
        else:
            feat.append(0.0)
    return np.array(feat).reshape(1, -1)


def predict_quality(txt_filepath, model_dir="models"):
    """
    Parameters
    ----------
    txt_filepath : str
        Path file .txt pembacaan sensor baru (format sama dengan data training)
    model_dir : str
        Folder tempat rf_quality_model.pkl, scaler.pkl, label_encoder.pkl,
        feature_columns.pkl disimpan (hasil train_model.py)

    Returns
    -------
    dict: {"predicted_label": str, "probabilities": dict}
    """
    model = joblib.load(os.path.join(model_dir, "rf_quality_model.pkl"))
    scaler = joblib.load(os.path.join(model_dir, "scaler.pkl"))
    le = joblib.load(os.path.join(model_dir, "label_encoder.pkl"))

    readings = _parse_txt_file(txt_filepath)
    X = _extract_features_single(readings)
    X_scaled = scaler.transform(X)

    pred_idx = model.predict(X_scaled)[0]
    pred_label = le.inverse_transform([pred_idx])[0]

    proba = model.predict_proba(X_scaled)[0]
    proba_dict = {cls: float(p) for cls, p in zip(le.classes_, proba)}

    return {"predicted_label": pred_label, "probabilities": proba_dict}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Cara pakai: python -m src.predict <path_file_sensor_baru.txt>")
        sys.exit(1)

    result = predict_quality(sys.argv[1])
    print(f"Prediksi kualitas/cacat mutu: {result['predicted_label']}")
    print("Probabilitas tiap kelas:")
    for k, v in result["probabilities"].items():
        print(f"  {k}: {v:.3f}")
