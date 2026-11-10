"""Controlled feature ablation on QC-valid sorted Smart Coffee 30-cycle CSVs.

Main question: do peak collecting response, collecting area (trapezoid),
and cycle-to-cycle baseline variability help beyond the existing 3 features
per sensor? Includes individual + joint additions to 3 core sensors and
all 10 sensors. One recording is one sample. Cohorts a,b=train; c=holdout.
The scaler is fit only in training fold/train. Holdout c is NOT for selection.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score, recall_score
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from benchmark_sorted_30cycle_readiness import prepare, LABELS, ORIGINS, SENSORS
from merge_new_30_siklus_audit import checksum

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/dataset sorting"
SOURCE_QA = ROOT / "results/dataset_sorting_readiness_20261110"
OUT = ROOT / "results/sorted_feature_ablation_20261110"
CORE = ["adc_tgs822", "adc_tgs2602", "adc_tgs816"]
BASE = ["median_phase_response", "mean_phase_response", "response_early_late"]
EXTRA = ["peak_response", "collect_auc_trapz", "baseline_iqr_30cycles"]


def extra_features(v: np.ndarray) -> dict:
    """30 cycles x (25 purge + 5 collect), one physical recording."""
    assert v.shape == (30, 30) and np.isfinite(v).all()
    b = np.median(v[:, 20:25], axis=1)  # purge idx 21..25 per cycle
    collecting = v[:, 25:30] - b[:, None]  # 30 x 5 samples
    # The five observed samples span FOUR 1-s intervals. No fictitious t=0.
    signed_auc = (0.5 * collecting[:, 0] + collecting[:, 1] +
                  collecting[:, 2] + collecting[:, 3] +
                  0.5 * collecting[:, 4])  # ADC*s, dt=1s
    return {
        "peak_response": float(np.median(np.max(collecting, axis=1))),
        "collect_auc_trapz": float(np.median(signed_auc)),
        "baseline_iqr_30cycles": float(np.percentile(b, 75) - np.percentile(b, 25)),
    }


def metric(y, pred):
    per_class = recall_score(y, pred, labels=LABELS, average=None, zero_division=0)
    return {
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "macro_f1": float(f1_score(y, pred, labels=LABELS, average="macro", zero_division=0)),
        "accuracy": float(accuracy_score(y, pred)),
        **{f"recall_{cls}": float(recall) for cls, recall in zip(LABELS, per_class)},
    }


def algorithm(name):
    return make_pipeline(
        StandardScaler(),  # fitted only on each training fold or entire a+b
        (LogisticRegression(max_iter=4000, C=1, class_weight="balanced")
         if name == "LogReg_L2" else SVC(C=1, gamma="scale", class_weight="balanced")),
    )


def cols(sensors, features):
    return [f"{feat}__{sensor}" for sensor in sensors for feat in features]


def run():
    if OUT.exists():
        raise FileExistsError("Existing results protected: " + str(OUT))
    # Use exact same inclusion and duplicate rules as the previous experiment.
    t, dup = prepare()
    a = pd.read_csv(SOURCE_QA / "all_csv_audit.csv")
    valid = a[(a.sort_status == "kept") & a.structurally_valid].copy()
    lookups = valid.set_index("filename")
    assert lookups.index.is_unique
    blocked = set(a.loc[(a.sort_status == "kept") & ~a.structurally_valid, "filename"])
    assert len(t) == 199 and len(blocked) == 4
    assert set(t.filename).isdisjoint(blocked)
    assert [x.filename for x in dup.itertuples()] == ["M-TEM_B62_20261019_175906.csv"]
    extra_rows = []
    for idx, filename in enumerate(t.filename):
        row = lookups.loc[filename]
        path = SOURCE / row.relative_path
        if not path.is_file() or checksum(path) != row.sha256:
            raise RuntimeError("Source changed: " + str(path))
        data = pd.read_csv(path)
        assert len(data) == 900
        assert data.phase.to_numpy().reshape(30, 30)[:, :25].tolist() == [["purging"]*25]*30
        assert data.phase.to_numpy().reshape(30, 30)[:, 25:].tolist() == [["collecting"]*5]*30
        out = {"filename": filename}
        for s in SENSORS:
            v = data[s].to_numpy(dtype=float).reshape(30, 30)
            for name, value in extra_features(v).items():
                out[f"{name}__{s}"] = value
        extra_rows.append(out)
        if (idx + 1) % 50 == 0:
            print("FEATURES_EXTRACTED", idx+1, len(t), flush=True)
    extras = pd.DataFrame(extra_rows)
    t = t.merge(extras, on="filename", validate="one_to_one")
    assert len(t) == 199 and not t.isna().any().any()
    assert set(t.cohort) == {"a", "b", "c"}
    train = t[t.cohort.isin(["a", "b"])].copy()
    test = t[t.cohort == "c"].copy()
    assert len(train) == 133 and len(test) == 66
    assert set(train.batch).isdisjoint(test.batch)
    assert train.origin.nunique() == 6
    assert all(train.groupby("roast").size().reindex(LABELS).gt(0))
    assert set(test.roast) == set(LABELS)

    feature_sets = {
        "CORE3_F9_BASE": cols(CORE, BASE),
        "CORE3_F12_PEAK": cols(CORE, BASE + [EXTRA[0]]),
        "CORE3_F12_AREA": cols(CORE, BASE + [EXTRA[1]]),
        "CORE3_F12_BASELINE_IQR": cols(CORE, BASE + [EXTRA[2]]),
        "CORE3_F15_PEAK_AREA": cols(CORE, BASE + EXTRA[:2]),
        "CORE3_F15_PEAK_BASELINE_IQR": cols(CORE, BASE + [EXTRA[0],EXTRA[2]]),
        "CORE3_F15_AREA_BASELINE_IQR": cols(CORE, BASE + [EXTRA[1],EXTRA[2]]),
        "CORE3_F18_ALL": cols(CORE, BASE + EXTRA),
        "ALL10_F30_BASE": cols(SENSORS, BASE),
        "ALL10_F40_PEAK": cols(SENSORS, BASE + [EXTRA[0]]),
        "ALL10_F40_AREA": cols(SENSORS, BASE + [EXTRA[1]]),
        "ALL10_F40_BASELINE_IQR": cols(SENSORS, BASE + [EXTRA[2]]),
        "ALL10_F60_ALL": cols(SENSORS, BASE + EXTRA),
    }
    rows, predictions, per_origin, out_of_cv = [], [], [], []
    fold_indices = list(LeaveOneGroupOut().split(train, train.roast, train.origin))
    assert len(fold_indices) == 6
    for config, fs in feature_sets.items():
        for model_name in ["LogReg_L2", "SVM_RBF"]:
            Xtr = train[fs].to_numpy(dtype=float)
            Xte = test[fs].to_numpy(dtype=float)
            ytr = train.roast.to_numpy()
            yte = test.roast.to_numpy()
            out = np.empty(len(train), dtype=object)
            for tr, val in fold_indices:
                assert set(train.origin.iloc[tr]).isdisjoint(train.origin.iloc[val])
                model = algorithm(model_name)
                model.fit(Xtr[tr], ytr[tr])
                out[val] = model.predict(Xtr[val])
            cv = metric(ytr, out)
            model = algorithm(model_name).fit(Xtr, ytr)
            p = model.predict(Xte)
            hold = metric(yte, p)
            conf = confusion_matrix(yte, p, labels=LABELS).tolist()
            rows.append({"configuration":config,"model":model_name,"feature_count":len(fs),
                        "train_n":len(train),"test_n":len(test),
                        **{f"train_logo_{k}":v for k,v in cv.items()},
                        **{f"holdout_c_{k}":v for k,v in hold.items()},
                        "holdout_c_confusion_matrix":json.dumps(conf)})
            for fn, gt, pred in zip(train.filename, ytr, out):
                out_of_cv.append({"configuration":config,"model":model_name,
                                  "filename":fn,"truth":gt,"train_origin_cv_pred":pred})
            for fn, origin, gt, pred in zip(test.filename, test.origin, yte, p):
                predictions.append({"configuration":config,"model":model_name,"filename":fn,
                                   "origin":origin,"truth":gt,"holdout_c_pred":pred})
            for orig, g in test.groupby("origin"):
                ix = test.index.get_indexer(g.index)
                per_origin.append({"configuration":config,"model":model_name,"origin":orig,
                                  "n_test":len(g),"classes_present":",".join(sorted(set(g.roast))),
                                  **metric(g.roast.to_numpy(), p[ix])})
            print("COMPARE",config,model_name,"CV",round(cv["balanced_accuracy"],4),
                  "C",round(hold["balanced_accuracy"],4),
                  "RECALL", [round(hold[f"recall_{x}"],3) for x in LABELS],flush=True)
    result = pd.DataFrame(rows)
    # Inspect feature redundancy using TRAIN only, not held-out c.
    redundancy = []
    for s in SENSORS:
        for feature in EXTRA:
            xs = train[f"{feature}__{s}"]
            ys = train[f"mean_phase_response__{s}"]
            corr = float(xs.corr(ys))
            redundancy.append({"sensor":s,"extra_feature":feature,
                               "correlation_with_mean_response_train":corr,
                               "absolute_correlation":abs(corr)})
    redund = pd.DataFrame(redundancy)

    OUT.mkdir(parents=True)
    t.to_csv(OUT/"recording_features_extracted.csv",index=False,encoding="utf-8-sig")
    result.to_csv(OUT/"ablation_model_scores.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(predictions).to_csv(OUT/"holdout_c_predictions.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(out_of_cv).to_csv(OUT/"train_origin_cv_predictions.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(per_origin).to_csv(OUT/"holdout_c_per_origin.csv",index=False,encoding="utf-8-sig")
    redund.to_csv(OUT/"feature_redundancy_training_only.csv",index=False,encoding="utf-8-sig")
    (OUT/"feature_sets.json").write_text(json.dumps(feature_sets,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    summary = {
        "train_count":len(train),"holdout_c_count":len(test),
        "excluded_incomplete_kept":sorted(blocked),
        "removed_duplicate_batch":[r.filename for r in dup.itertuples()],
        "core_sensors":CORE,"all_sensors":SENSORS,"old_features":BASE,"added_features":EXTRA,
        "peak":"median across 30 cycles of max(collecting ADC[1..5] minus per-cycle purge baseline)",
        "area":"median across cycles of signed trapezoidal AUC on five corrected collecting samples, 4 seconds observed span, ADC*s",
        "baseline_var":"IQR of 30 per-cycle median purge[21..25] values, ADC",
        "preprocess":"per-cycle baseline correction before record feature extraction; global StandardScaler fit only on training",
        "train_val":"cohorts a+b, leave-one-origin-out CV with training-only scaling in each fold",
        "holdout":"cohort c B80-B90 kept+valid. Incomplete and duplicate batch IDs excluded.",
        "selection_rule":"select model and features on training CV; cohort c scores are diagnostic and not final unbiased model selection",
        "important_limitations":["Only manual-kept records, cohort c is human-selected.",
            "Some origin x roast combinations absent in cohort c.",
            "Device metadata absent in a and c, and label-device confounded in b.",
            "Batch IDs do not prove physical specimen independence.",
            "Median area is inherently correlated to mean phase response on 5-point collecting segments.",
            "Only a future prospective test can validate deployment performance."
        ],
    }
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    # Figure: train-only CV grouped configurations; holdout is supplementary
    display=result[result.configuration.str.startswith("CORE3_")].copy()
    display["configuration"]=display.configuration.str.replace("CORE3_", "", regex=False)
    piv=display.pivot(index="configuration",columns="model",values="train_logo_balanced_accuracy")
    fig,ax=plt.subplots(figsize=(12,5.8),dpi=145)
    pos=np.arange(len(piv));w=.36
    ax.bar(pos-w/2,piv["LogReg_L2"].values*100,width=w,label="Logistic Regression L2",color="#246B88")
    ax.bar(pos+w/2,piv["SVM_RBF"].values*100,width=w,label="SVM RBF",color="#D4A441")
    ax.axhline(100/3,ls="--",color="#999999",label="Peluang seimbang 3 kelas")
    ax.set_xticks(pos,piv.index.tolist(),rotation=30,ha="right")
    ax.set_ylabel("Balanced accuracy CV training lintas origin (%)")
    ax.set_title("Ablation fitur 3 sensor — validasi training saja (a+b)")
    ax.legend(ncol=3,loc="upper right",fontsize=9)
    ax.grid(axis="y",alpha=.15)
    fig.tight_layout()
    fig.savefig(OUT/"feature_ablation_train_cv.png");plt.close(fig)
    print("FINISHED",json.dumps({
        "configs":len(feature_sets),"models":len(result),"old_core":result[result.configuration=="CORE3_F9_BASE"][["model","train_logo_balanced_accuracy","holdout_c_balanced_accuracy"]].to_dict("records"),
        "best_train_cv":result.sort_values("train_logo_balanced_accuracy",ascending=False).iloc[0][["configuration","model","train_logo_balanced_accuracy","holdout_c_balanced_accuracy"]].to_dict(),
        "max_abs_area_corr":float(redund[redund.extra_feature=="collect_auc_trapz"].absolute_correlation.max()),
    }),flush=True)
    return result


if __name__ == "__main__":
    run()
