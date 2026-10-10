"""Benchmark khusus data asli Zenodo; BUKAN penambahan training sensor ATmega.

Satu observasi = 10 langkah heater BME688. Random stratified vs tail per
kelas (proxy urutan; sesi fisik tidak tersedia). Tidak pakai data dummy.
Tidak membuat/menyimpan model untuk deployment.
"""

from __future__ import annotations

import argparse
import json
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score,
    precision_recall_fscore_support,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from research_external_coffee_datasets import DATASETS, verify_bytes

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = ROOT / "data/external/zenodo_15425922"
SEED = 20261010
STEPS = 10
FILES = ("dataset_integrity.csv", "evaluation_metrics.csv",
         "per_class_metrics.csv", "split_manifest.csv", "summary.json")


def load_data(folder: Path, name: str) -> tuple[np.ndarray, np.ndarray, dict]:
    """Never silently repair missing data; quarantine only incomplete tail."""
    spec = DATASETS[name]
    path = folder / spec["filename"]
    raw = path.read_bytes()
    sha = verify_bytes(raw, spec["md5"])
    data = pd.read_csv(path)
    if list(data.columns) != ["Resistance Gassensor", "label"]:
        raise ValueError("Unexpected external CSV schema")
    val = pd.to_numeric(data.iloc[:, 0], errors="raise").to_numpy(dtype=float)
    lab = pd.to_numeric(data.iloc[:, 1], errors="raise").to_numpy(dtype=float)
    if not np.isfinite(val).all() or not (val > 0).all():
        raise ValueError("Nonfinite/negative gas resistance")
    if not np.isfinite(lab).all() or not np.array_equal(
        lab, lab.astype(np.int64).astype(float)
    ):
        raise ValueError("Noninteger/missing labels")
    labels = lab.astype(np.int64)
    if name == "CoffeePow-4" and set(labels) != {0, 1, 2, 3}:
        raise ValueError("CoffeePow-4 classes changed")
    if name == "Aroma-7" and set(labels) != set(range(7)):
        raise ValueError("Aroma-7 classes changed")
    full = len(val) // STEPS
    kept = full * STEPS
    incomplete = len(val) - kept
    if name == "CoffeePow-4" and incomplete != 0:
        raise ValueError("Unexpected incomplete CoffeePow-4 signal")
    if name == "Aroma-7" and incomplete != 4:
        raise ValueError("Unexpected Aroma-7 tail; inspect before analysis")
    seq = val[:kept].reshape(full, STEPS)
    grouped = labels[:kept].reshape(full, STEPS)
    if not (grouped == grouped[:, :1]).all():
        raise ValueError("Class label changed within a sensor heater cycle")
    y = grouped[:, 0]
    return seq, y, {
        "dataset": name, "doi": spec["doi"], "sha256": sha,
        "publisher_md5_verified": spec["md5"], "rows_raw": len(val),
        "complete_sequences": full, "sample_steps_per_sequence": STEPS,
        "discarded_from_analysis_incomplete_tail_rows": incomplete,
        "class_counts": {str(k): int(v) for k, v in
                         sorted(pd.Series(y).value_counts().items())},
        "file": spec["filename"],
    }


def split_indices(y: np.ndarray, strategy: str
                  ) -> tuple[np.ndarray, np.ndarray]:
    ix = np.arange(len(y))
    if strategy == "stratified_random":
        tr, te = train_test_split(
            ix, test_size=0.2, stratify=y, random_state=SEED
        )
        return np.sort(tr), np.sort(te)
    if strategy == "within_class_tail":
        train, test = [], []
        for cl in np.unique(y):
            ordered = ix[y == cl]
            n_test = max(1, int(np.ceil(len(ordered) * 0.2)))
            train.extend(ordered[:-n_test])
            test.extend(ordered[-n_test:])
        tr = np.array(sorted(train), dtype=int)
        te = np.array(sorted(test), dtype=int)
        if len(set(tr).intersection(te)):
            raise ValueError("Split overlap")
        return tr, te
    raise ValueError("Unknown split strategy")


def algorithms() -> dict:
    return {
        "dummy_prior": DummyClassifier(strategy="prior"),
        "logistic": Pipeline([
            ("scale", StandardScaler()),
            ("model", LogisticRegression(C=1.0, max_iter=2500,
                                         random_state=SEED)),
        ]),
        "lda_shrinkage": Pipeline([
            ("scale", StandardScaler()),
            ("model", LinearDiscriminantAnalysis(
                solver="lsqr", shrinkage="auto",
            )),
        ]),
        "svm_rbf": Pipeline([
            ("scale", StandardScaler()),
            ("model", SVC(C=1.0, gamma="scale")),
        ]),
        "random_forest": RandomForestClassifier(
            n_estimators=80, min_samples_leaf=3, n_jobs=1,
            random_state=SEED,
        ),
    }


def evaluation_targets(dataset: str, labels: np.ndarray) -> dict[str, np.ndarray]:
    # This mapping is based on class order described in the paper's
    # source README; unlike a specimen ID it is not verified sample by sample.
    if dataset == "CoffeePow-4":
        return {
            "4class_dataset_codes": labels.astype(str),
            "air0_vs_coffee123_assumed_author_order": np.where(
                labels == 0, "air_index0", "coffee_indices123"
            ),
        }
    return {
        "7class_dataset_codes": labels.astype(str),
        "noncoffee_0_4_5_6_vs_coffee123_assumed_author_order": np.where(
            np.isin(labels, [1, 2, 3]), "coffee_indices123",
            "air_or_cream_indices0456",
        ),
    }


def duplicate_rows_across_split(X: np.ndarray, tr: np.ndarray,
                                te: np.ndarray) -> int:
    signatures = {hashlib.sha256(row.tobytes()).digest() for row in X[tr]}
    return sum(hashlib.sha256(row.tobytes()).digest() in signatures for row in X[te])


def evaluate_one(X: np.ndarray, y: np.ndarray, dataset: str,
                 target_name: str, split: str,
                 models: dict | None = None) -> tuple[list[dict], list[dict], pd.DataFrame]:
    if models is None:
        models = algorithms()
    tr, te = split_indices(y, split)
    if not set(y[tr]) == set(y[te]) or not set(y[tr]) == set(y):
        raise ValueError("A class missing in train or test")
    if np.intersect1d(tr, te).size or len(np.union1d(tr, te)) != len(y):
        raise ValueError("Train/test leakage/coverage")
    # Feature engineering without fitting on the test data; log is physical
    # transformation of strictly positive Ohm values, scaler fits train only.
    transformed = np.log10(X)
    labels = sorted(set(y))
    metrics, classes = [], []
    duplicates = duplicate_rows_across_split(X, tr, te)
    for name, prototype in models.items():
        model = clone(prototype)
        model.fit(transformed[tr], y[tr])
        prediction = model.predict(transformed[te])
        metrics.append({
            "dataset": dataset, "target": target_name,
            "split": split, "model": name,
            "n_train": len(tr), "n_test": len(te),
            "duplicate_test_sequences_exact_in_train": duplicates,
            "accuracy": float(accuracy_score(y[te], prediction)),
            "macro_f1": float(f1_score(
                y[te], prediction, labels=labels,
                average="macro", zero_division=0,
            )),
            "balanced_accuracy": float(balanced_accuracy_score(
                y[te], prediction
            )),
            "confusion_labels": json.dumps(labels),
            "confusion_matrix": json.dumps(
                confusion_matrix(y[te], prediction, labels=labels).tolist()
            ),
            "status": "EXTERNAL_DEVICE_ONLY_NOT_LOCAL_HARDWARE_ACCURACY",
        })
        precision, recall, f1, support = precision_recall_fscore_support(
            y[te], prediction, labels=labels, zero_division=0,
        )
        for i, label in enumerate(labels):
            classes.append({
                "dataset": dataset, "target": target_name,
                "split": split, "model": name, "label": label,
                "precision": float(precision[i]), "recall": float(recall[i]),
                "f1": float(f1[i]), "support": int(support[i]),
            })
    manifest = pd.DataFrame({
        "dataset": dataset, "target": target_name,
        "split": split, "record_sequence_index": np.arange(len(y)),
        "label": y, "partition": "train",
    })
    manifest.loc[te, "partition"] = "test"
    return metrics, classes, manifest


def verify_overlap(coffee: np.ndarray, yc: np.ndarray,
                   aroma: np.ndarray, ya: np.ndarray) -> bool:
    if not np.array_equal(coffee, aroma[:len(coffee)]) or not np.array_equal(
        yc, ya[:len(yc)]
    ):
        raise ValueError("Aroma-7 overlapping CoffeePow-4 content changed")
    return True


def run(folder: Path) -> tuple[dict, dict]:
    all_samples, all_labels = {}, {}
    integrity = []
    for dataset in DATASETS:
        sample, labels, stat = load_data(folder, dataset)
        all_samples[dataset], all_labels[dataset] = sample, labels
        integrity.append(stat)
    overlap = verify_overlap(
        all_samples["CoffeePow-4"], all_labels["CoffeePow-4"],
        all_samples["Aroma-7"], all_labels["Aroma-7"],
    )
    metrics, classes, partitions = [], [], []
    for ds in DATASETS:
        for task, target in evaluation_targets(ds, all_labels[ds]).items():
            for scheme in ("stratified_random", "within_class_tail"):
                m, c, s = evaluate_one(
                    all_samples[ds], target, ds, task, scheme
                )
                metrics.extend(m)
                classes.extend(c)
                partitions.append(s)
    results = pd.DataFrame(metrics)
    focus = results.loc[
        results["model"].ne("dummy_prior") &
        results["target"].str.contains("vs_coffee") &
        results["split"].eq("within_class_tail")
    ].sort_values(["dataset", "macro_f1"], ascending=[True, False])
    summary = {
        "status": "REAL_EXTERNAL_DATA_VERIFIED_BENCHMARK_EXPLORATORY_ONLY",
        "zenodo_doi": "10.5281/zenodo.15425922",
        "paper_doi": "10.1016/j.rineng.2025.106309",
        "datasets": integrity,
        "coffee_pow4_included_identically_in_aroma7": overlap,
        "aroma7_partial_tail_preserved_raw_but_held": 4,
        "sensor_protocol": "BME688 10-step heater cycle resistance; NOT MCU MQ/TGS 1Hz purging/collecting",
        "label_mapping": "index interpretation inferred from author's published README class order; not a roast label",
        "session_ids_provided": False,
        "physical_specimen_independent_holdout": False,
        "scaling_training_only": True,
        "external_data_added_to_local_roast_training": False,
        "local_model_approval": "NO_GO",
        "evaluation_rows": len(results),
        "non_dummy_binary_tail_comparisons": focus[[
            "dataset", "target", "model", "macro_f1",
            "balanced_accuracy", "accuracy"
        ]].to_dict("records"),
    }
    outputs = {
        "dataset_integrity.csv": pd.DataFrame([{
            **{k: v for k, v in stat.items() if k != "class_counts"},
            "class_counts_json": json.dumps(stat["class_counts"])
        } for stat in integrity]),
        "evaluation_metrics.csv": results,
        "per_class_metrics.csv": pd.DataFrame(classes),
        "split_manifest.csv": pd.concat(partitions, ignore_index=True),
        "summary.json": summary,
    }
    return outputs, summary


def save(folder: Path, outputs: dict) -> None:
    path = folder.resolve()
    if path.exists():
        raise FileExistsError("Use new result directory, never overwrite")
    if path == (ROOT / "data/raw").resolve() or (
        (ROOT / "data/raw").resolve() in path.parents
    ):
        raise ValueError("Cannot write external results into local sensor raw")
    path.mkdir(parents=True, exist_ok=False)
    for file in FILES:
        obj = outputs[file]
        if file.endswith(".json"):
            (path / file).write_text(
                json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False)+"\n",
                encoding="utf-8",
            )
        else:
            obj.to_csv(path / file, index=False, float_format="%.12g")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-dir", type=Path, default=EXTERNAL)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    outputs, summary = run(args.source_dir)
    save(args.output_dir, outputs)
    print("EXTERNAL_PUBLISHED_REAL_SENSOR_DATA_BENCHMARK_PASS")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
