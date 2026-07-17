"""
train_model.py
---------------
Melatih Random Forest untuk klasifikasi kualitas/cacat mutu kopi
(Adulterated Quality / High Quality / Low Quality) berdasarkan fitur
statistik dari 8 sensor e-nose.
"""

import os
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, GridSearchCV, StratifiedKFold
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder

from src.feature_extraction import get_feature_columns


def train_random_forest(df, model_dir="models", test_size=0.2, random_state=42,
                         use_grid_search=True):
    """
    Melatih RandomForestClassifier dan menyimpan model + scaler + label
    encoder ke model_dir.

    Parameters
    ----------
    df : pd.DataFrame
        Output dari feature_extraction.extract_features()
    model_dir : str
        Folder tujuan penyimpanan model (.pkl)
    test_size : float
    random_state : int
    use_grid_search : bool
        Kalau True, cari hyperparameter terbaik lewat GridSearchCV
        (butuh data agak banyak; kalau data sedikit, set False).

    Returns
    -------
    dict berisi model, scaler, label_encoder, X_test, y_test, y_pred
    """
    os.makedirs(model_dir, exist_ok=True)

    feature_cols = get_feature_columns(df)
    X = df[feature_cols].values
    y_raw = df["quality_label"].values

    le = LabelEncoder()
    y = le.fit_transform(y_raw)

    # Stratify supaya proporsi tiap kelas roasting tetap terjaga di train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    if use_grid_search:
        param_grid = {
            "n_estimators": [100, 200, 400],
            "max_depth": [None, 5, 10, 20],
            "min_samples_split": [2, 4],
            "min_samples_leaf": [1, 2],
        }
        cv = StratifiedKFold(n_splits=min(5, np.bincount(y_train).min()), shuffle=True,
                              random_state=random_state)
        base_model = RandomForestClassifier(random_state=random_state, class_weight="balanced")
        grid = GridSearchCV(base_model, param_grid, cv=cv, scoring="f1_macro",
                             n_jobs=-1, verbose=1)
        grid.fit(X_train_scaled, y_train)
        model = grid.best_estimator_
        print(f"[INFO] Best params: {grid.best_params_}")
    else:
        model = RandomForestClassifier(
            n_estimators=300, random_state=random_state, class_weight="balanced"
        )
        model.fit(X_train_scaled, y_train)

    y_pred = model.predict(X_test_scaled)

    # Simpan artefak
    joblib.dump(model, os.path.join(model_dir, "rf_quality_model.pkl"))
    joblib.dump(scaler, os.path.join(model_dir, "scaler.pkl"))
    joblib.dump(le, os.path.join(model_dir, "label_encoder.pkl"))
    joblib.dump(feature_cols, os.path.join(model_dir, "feature_columns.pkl"))
    print(f"[INFO] Model & artefak disimpan di: {model_dir}")

    return {
        "model": model,
        "scaler": scaler,
        "label_encoder": le,
        "feature_cols": feature_cols,
        "X_test": X_test_scaled,
        "y_test": y_test,
        "y_pred": y_pred,
    }
