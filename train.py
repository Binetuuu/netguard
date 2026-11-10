"""Train and evaluate NetGuard on NSL-KDD.

Pipeline:
  1. Preprocess (log1p on heavy-tailed counters, one-hot on protocol/service/flag)
  2. Baseline: XGBoost without any imbalance handling
  3. NetGuard: SMOTE (R2L, U2R oversampled) + cost-sensitive XGBoost
  4. Novelty layer: Isolation Forest trained on normal traffic only, to catch
     attacks the classifier has never seen (zero-day style patterns)
Evaluated on KDDTest+, which contains 17 attack types absent from training.

Usage:  python train.py
"""
import json
import os
import time

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from imblearn.over_sampling import SMOTE
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (classification_report, confusion_matrix, f1_score,
                             recall_score, precision_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

from netguard_core import (CATEGORICAL, CLASSES, FEATURES, NUMERIC,
                           load_nsl_kdd, transform_numeric)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "artifacts")
os.makedirs(OUT, exist_ok=True)
RNG = 42


def build_preprocessor():
    return Pipeline([
        ("log", FunctionTransformer(transform_numeric)),
        ("ct", ColumnTransformer([
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
            ("num", "passthrough", NUMERIC),
        ])),
    ])


def xgb():
    return XGBClassifier(
        n_estimators=300, max_depth=8, learning_rate=0.1, subsample=0.9,
        colsample_bytree=0.8, tree_method="hist", objective="multi:softprob",
        num_class=len(CLASSES), random_state=RNG, n_jobs=-1, eval_metric="mlogloss",
    )


def evaluate(name, y_true, y_pred):
    rep = classification_report(y_true, y_pred, labels=range(len(CLASSES)),
                                target_names=CLASSES, output_dict=True, zero_division=0)
    bin_true = (y_true != 0).astype(int)
    bin_pred = (y_pred != 0).astype(int)
    res = {
        "macro_f1": f1_score(y_true, y_pred, average="macro"),
        "weighted_f1": f1_score(y_true, y_pred, average="weighted"),
        "accuracy": float((y_true == y_pred).mean()),
        "per_class_recall": {c: rep[c]["recall"] for c in CLASSES},
        "per_class_f1": {c: rep[c]["f1-score"] for c in CLASSES},
        "attack_detection_rate": recall_score(bin_true, bin_pred),
        "false_alarm_rate": float(((bin_pred == 1) & (bin_true == 0)).sum() / max((bin_true == 0).sum(), 1)),
        "attack_precision": precision_score(bin_true, bin_pred),
    }
    print(f"\n=== {name} ===")
    print(classification_report(y_true, y_pred, labels=range(len(CLASSES)),
                                target_names=CLASSES, zero_division=0, digits=3))
    print(f"Detection rate {res['attack_detection_rate']:.3f} | false alarms {res['false_alarm_rate']:.3f}")
    return res


def main():
    t0 = time.time()
    train = load_nsl_kdd(os.path.join(DATA, "KDDTrain+.txt"))
    test = load_nsl_kdd(os.path.join(DATA, "KDDTest+.txt"))
    cls_idx = {c: i for i, c in enumerate(CLASSES)}
    y_train = train["family"].map(cls_idx).values
    y_test = test["family"].map(cls_idx).values

    unseen_types = sorted(set(test["attack"]) - set(train["attack"]))
    print("Train class counts:", train["family"].value_counts().to_dict())
    print("Test class counts :", test["family"].value_counts().to_dict())
    print(f"{len(unseen_types)} attack types in test never seen in training: {unseen_types}")

    pre = build_preprocessor()
    X_train = pre.fit_transform(train[FEATURES])
    X_test = pre.transform(test[FEATURES])
    feat_names = [n.split("__", 1)[1] for n in pre.named_steps["ct"].get_feature_names_out()]

    # ---- 1. Baseline -------------------------------------------------------
    base = xgb().fit(X_train, y_train)
    p_base = base.predict(X_test)
    m_base = evaluate("Baseline XGBoost (no imbalance handling)", y_test, p_base)

    # ---- 2. NetGuard: SMOTE + cost-sensitive -------------------------------
    counts = np.bincount(y_train)
    target = {cls_idx["R2L"]: max(counts[cls_idx["R2L"]], 8000),
              cls_idx["U2R"]: max(counts[cls_idx["U2R"]], 3000)}
    X_res, y_res = SMOTE(sampling_strategy=target, k_neighbors=5,
                         random_state=RNG).fit_resample(X_train, y_train)
    print("After SMOTE:", dict(zip(CLASSES, np.bincount(y_res))))
    sw = compute_sample_weight("balanced", y_res) ** 0.5  # softened class weights
    clf = xgb().fit(X_res, y_res, sample_weight=sw)
    proba = clf.predict_proba(X_test)
    p_ng = proba.argmax(1)
    m_ng = evaluate("NetGuard classifier (SMOTE + cost-sensitive)", y_test, p_ng)

    # ---- 3. Novelty layer (Isolation Forest on normal traffic) -------------
    normal_mask = y_train == 0
    X_norm = X_train[normal_mask]
    rng = np.random.default_rng(RNG)
    idx = rng.permutation(len(X_norm))
    fit_idx, val_idx = idx[: int(0.8 * len(idx))], idx[int(0.8 * len(idx)):]
    iso = IsolationForest(n_estimators=200, random_state=RNG, n_jobs=-1).fit(X_norm[fit_idx])
    # threshold = 2nd percentile of held-out normal scores (≈2% false alarms on known-normal)
    iso_thr = float(np.percentile(iso.score_samples(X_norm[val_idx]), 2))
    iso_flag = iso.score_samples(X_test) < iso_thr

    # Hybrid decision: if classifier says "normal" but either the anomaly detector
    # fires or the classifier is unsure, raise it as a (generic) suspicious event.
    conf_thr = 0.80
    suspicious = (p_ng == 0) & (iso_flag | (proba[:, 0] < conf_thr))
    p_hyb = p_ng.copy()
    # count suspicious as "attack" for binary metrics; family unknown -> keep 2nd best class
    second = np.argsort(proba, axis=1)[:, -2]
    p_hyb[suspicious] = second[suspicious]
    m_hyb = evaluate("NetGuard hybrid (classifier + novelty detector)", y_test, p_hyb)

    unseen_mask = test["attack"].isin(unseen_types).values
    det_unseen = {
        "baseline": float((p_base[unseen_mask] != 0).mean()),
        "netguard_classifier": float((p_ng[unseen_mask] != 0).mean()),
        "netguard_hybrid": float((p_hyb[unseen_mask] != 0).mean()),
        "n_samples": int(unseen_mask.sum()),
    }
    print("Detection rate on never-seen attack types:", det_unseen)

    # ---- Plots ---------------------------------------------------------------
    # per-class recall comparison
    fig, ax = plt.subplots(figsize=(8, 4.2))
    w = 0.27
    x = np.arange(len(CLASSES))
    for i, (lab, m, col) in enumerate([("Baseline", m_base, "#9aa5b1"),
                                        ("NetGuard (SMOTE)", m_ng, "#2f6fd6"),
                                        ("NetGuard hybride", m_hyb, "#0f9d74")]):
        vals = [m["per_class_recall"][c] for c in CLASSES]
        ax.bar(x + (i - 1) * w, vals, w, label=lab, color=col)
    ax.set_xticks(x, CLASSES)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Rappel (taux de détection)")
    ax.set_title("Rappel par famille d'attaque — KDDTest+")
    ax.legend(frameon=False, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "recall_comparison.png"), dpi=160)
    plt.close(fig)

    # confusion matrix (hybrid, row-normalized)
    cm = confusion_matrix(y_test, p_hyb, labels=range(len(CLASSES)))
    cmn = cm / cm.sum(1, keepdims=True)
    fig, ax = plt.subplots(figsize=(5.4, 4.6))
    im = ax.imshow(cmn, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(CLASSES)), CLASSES)
    ax.set_yticks(range(len(CLASSES)), CLASSES)
    ax.set_xlabel("Prédit")
    ax.set_ylabel("Réel")
    for i in range(len(CLASSES)):
        for j in range(len(CLASSES)):
            ax.text(j, i, f"{cmn[i, j]:.2f}", ha="center", va="center",
                    color="white" if cmn[i, j] > 0.5 else "#1f2933", fontsize=9)
    ax.set_title("Matrice de confusion (normalisée) — NetGuard hybride")
    fig.colorbar(im, fraction=0.046)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "confusion_matrix.png"), dpi=160)
    plt.close(fig)

    # SHAP global importance
    sample = X_test[rng.choice(len(X_test), 600, replace=False)]
    explainer = shap.TreeExplainer(clf)
    sv = explainer.shap_values(sample)
    sv = np.array(sv)
    if sv.ndim == 3 and sv.shape[0] == len(CLASSES):  # (classes, n, f)
        sv = np.transpose(sv, (1, 2, 0))
    imp = np.abs(sv).mean(axis=(0, 2))
    order = np.argsort(imp)[::-1][:15]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.barh([feat_names[i] for i in order][::-1], imp[order][::-1], color="#2f6fd6")
    ax.set_xlabel("Importance moyenne |SHAP|")
    ax.set_title("Top 15 des variables qui expliquent les décisions")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "shap_importance.png"), dpi=160)
    plt.close(fig)

    # ---- Save ----------------------------------------------------------------
    joblib.dump({
        "preprocessor": pre, "classifier": clf, "iso": iso, "iso_threshold": iso_thr,
        "conf_threshold": conf_thr, "classes": CLASSES, "feature_names": feat_names,
    }, os.path.join(OUT, "netguard_model.joblib"), compress=3)

    metrics = {
        "baseline": m_base, "netguard_classifier": m_ng, "netguard_hybrid": m_hyb,
        "unseen_attack_detection": det_unseen, "unseen_attack_types": unseen_types,
        "train_counts": train["family"].value_counts().to_dict(),
        "test_counts": test["family"].value_counts().to_dict(),
        "smote_counts": dict(zip(CLASSES, map(int, np.bincount(y_res)))),
        "top_features": [feat_names[i] for i in order[:10]],
        "shap_importance": [[feat_names[i], float(imp[i])] for i in order[:15]],
        "confusion_matrix_hybrid": cm.tolist(),
    }
    with open(os.path.join(OUT, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, default=float)

    # demo file for the web app (stratified sample of the test set, with ground truth)
    demo = (test.groupby("family", group_keys=False)
                .apply(lambda g: g.sample(min(len(g), 160), random_state=RNG)))
    demo = demo.sample(frac=1, random_state=RNG)
    demo[FEATURES + ["attack"]].to_csv(os.path.join(DATA, "demo_traffic.csv"), index=False)
    print(f"\nDone in {time.time() - t0:.0f}s. Artifacts in {OUT}")


if __name__ == "__main__":
    main()
