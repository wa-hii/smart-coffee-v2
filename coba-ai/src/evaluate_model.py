"""
evaluate_model.py
------------------
Evaluasi hasil Random Forest: classification report, confusion matrix,
dan feature importance (fitur/sensor mana paling berpengaruh).
"""

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")  # aman dijalankan tanpa display (headless)
import matplotlib.pyplot as plt
from sklearn.metrics import classification_report, confusion_matrix, ConfusionMatrixDisplay


def evaluate(result, output_dir="outputs"):
    """
    Parameters
    ----------
    result : dict
        Output dari train_model.train_random_forest()
    output_dir : str
        Folder untuk menyimpan plot evaluasi
    """
    os.makedirs(output_dir, exist_ok=True)

    y_test = result["y_test"]
    y_pred = result["y_pred"]
    le = result["label_encoder"]
    model = result["model"]
    feature_cols = result["feature_cols"]

    target_names = le.classes_

    print("\n=== Classification Report ===")
    report = classification_report(y_test, y_pred, target_names=target_names)
    print(report)
    with open(os.path.join(output_dir, "classification_report.txt"), "w") as f:
        f.write(report)

    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=target_names)
    fig, ax = plt.subplots(figsize=(6, 5))
    disp.plot(ax=ax, cmap="Blues", colorbar=False)
    ax.set_title("Confusion Matrix - Coffee Quality Classification")
    plt.tight_layout()
    cm_path = os.path.join(output_dir, "confusion_matrix.png")
    plt.savefig(cm_path, dpi=150)
    plt.close(fig)
    print(f"[INFO] Confusion matrix disimpan: {cm_path}")

    # Feature importance (top 15)
    importances = model.feature_importances_
    idx = np.argsort(importances)[::-1][:15]
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh([feature_cols[i] for i in idx][::-1], importances[idx][::-1])
    ax.set_xlabel("Importance")
    ax.set_title("Top 15 Feature Importance - Random Forest")
    plt.tight_layout()
    fi_path = os.path.join(output_dir, "feature_importance.png")
    plt.savefig(fi_path, dpi=150)
    plt.close(fig)
    print(f"[INFO] Feature importance disimpan: {fi_path}")

    return {"classification_report": report, "confusion_matrix": cm}
