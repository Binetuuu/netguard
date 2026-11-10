"""NetGuard — Streamlit demo app.  Run:  streamlit run app.py"""
import json
import os

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import shap
import streamlit as st

from netguard_core import ADVICE, ATTACK_FAMILY, CLASSES, FEATURES

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "artifacts")
COLORS = {"normal": "#0f9d74", "DoS": "#d64545", "Probe": "#e8a23a",
          "R2L": "#7b5cd6", "U2R": "#1f2933", "Suspect (inconnu)": "#e05fa0"}

st.set_page_config(page_title="NetGuard – Détection d'intrusions", layout="wide")


@st.cache_resource
def load_model():
    return joblib.load(os.path.join(ART, "netguard_model.joblib"))


@st.cache_data
def load_metrics():
    with open(os.path.join(ART, "metrics.json"), encoding="utf-8") as f:
        return json.load(f)


@st.cache_resource
def get_explainer(_clf):
    return shap.TreeExplainer(_clf)


def predict(df: pd.DataFrame, m, conf_thr: float):
    X = m["preprocessor"].transform(df[FEATURES])
    proba = m["classifier"].predict_proba(X)
    pred = proba.argmax(1)
    iso_score = m["iso"].score_samples(X)
    iso_flag = iso_score < m["iso_threshold"]
    suspicious = (pred == 0) & (iso_flag | (proba[:, 0] < conf_thr))
    labels = np.array(CLASSES, dtype=object)[pred]
    labels[suspicious] = "Suspect (inconnu)"
    out = df.copy()
    out["verdict"] = labels
    out["confiance"] = proba.max(1).round(3)
    out["score_anomalie"] = (-iso_score).round(3)
    return out, X, proba


st.title("NetGuard")
st.caption("Détection d'intrusions réseau robuste aux données déséquilibrées et aux attaques inédites "
           "— DataNova 2026, problème DN-CY-01")

if not os.path.exists(os.path.join(ART, "netguard_model.joblib")):
    st.error("Modèle introuvable. Lancez d'abord `python train.py`.")
    st.stop()

m = load_model()
metrics = load_metrics()

with st.sidebar:
    st.header("Données à analyser")
    up = st.file_uploader("Fichier CSV de connexions (format NSL-KDD, 41 colonnes)", type=["csv"])
    st.caption("Sans fichier, un échantillon du jeu de test KDDTest+ est utilisé.")
    conf_thr = st.slider("Seuil de confiance « normal »", 0.5, 0.99,
                         float(m["conf_threshold"]), 0.01,
                         help="En dessous de ce seuil, une connexion classée normale est signalée comme suspecte.")
    st.divider()
    st.markdown("**Familles d'attaques**\n\n- **DoS** : déni de service\n- **Probe** : scan / reconnaissance\n"
                "- **R2L** : accès distant non autorisé\n- **U2R** : élévation de privilèges\n"
                "- **Suspect** : comportement anormal non reconnu (possible attaque inédite)")

if up is not None:
    df = pd.read_csv(up)
    missing = [c for c in FEATURES if c not in df.columns]
    if missing:
        if df.shape[1] in (41, 42, 43):  # raw NSL-KDD without header
            up.seek(0)
            df = pd.read_csv(up, header=None)
            df.columns = (FEATURES + ["attack", "difficulty"])[: df.shape[1]]
        else:
            st.error(f"Colonnes manquantes : {missing[:8]}…")
            st.stop()
else:
    df = pd.read_csv(os.path.join(HERE, "data", "demo_traffic.csv"))

res, X, proba = predict(df, m, conf_thr)

tab1, tab2, tab3, tab4 = st.tabs(["Analyse du trafic", "Expliquer une alerte",
                                  "Performance du modèle", "À propos"])

with tab1:
    n = len(res)
    n_alert = int((res["verdict"] != "normal").sum())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Connexions analysées", f"{n:,}".replace(",", " "))
    c2.metric("Alertes", n_alert, f"{n_alert / n:.1%} du trafic", delta_color="inverse")
    c3.metric("Critiques (U2R / R2L)", int(res["verdict"].isin(["U2R", "R2L"]).sum()))
    c4.metric("Suspects (inconnus)", int((res["verdict"] == "Suspect (inconnu)").sum()))

    if "attack" in res.columns:
        truth = res["attack"].map(ATTACK_FAMILY).fillna("R2L")
        is_att, flagged = truth != "normal", res["verdict"] != "normal"
        st.info(f"Vérité terrain disponible → taux de détection des attaques : "
                f"**{(flagged & is_att).sum() / max(is_att.sum(), 1):.1%}**, fausses alertes : "
                f"**{(flagged & ~is_att).sum() / max((~is_att).sum(), 1):.1%}**")

    left, right = st.columns([1, 1.3])
    counts = res["verdict"].value_counts().reset_index()
    counts.columns = ["verdict", "n"]
    left.plotly_chart(px.bar(counts, x="n", y="verdict", orientation="h", color="verdict",
                             color_discrete_map=COLORS, title="Répartition des verdicts")
                      .update_layout(showlegend=False, yaxis_title=None, xaxis_title="connexions"),
                      width="stretch")
    by_service = (res[res["verdict"] != "normal"].groupby(["service", "verdict"]).size()
                  .reset_index(name="n").sort_values("n", ascending=False).head(25))
    right.plotly_chart(px.bar(by_service, x="service", y="n", color="verdict",
                              color_discrete_map=COLORS, title="Services ciblés par les alertes")
                       .update_layout(xaxis_title=None, yaxis_title="alertes"),
                       width="stretch")

    st.subheader("Journal des alertes")
    only_alerts = st.checkbox("Afficher uniquement les alertes", value=True)
    view = res[res["verdict"] != "normal"] if only_alerts else res
    cols = ["verdict", "confiance", "score_anomalie", "protocol_type", "service", "flag",
            "src_bytes", "dst_bytes", "count", "serror_rate"] + (["attack"] if "attack" in res else [])
    st.dataframe(view[cols].rename(columns={"attack": "vérité terrain"}),
                 width="stretch", height=320)
    st.download_button("Télécharger le rapport (CSV)", res.to_csv(index=False).encode("utf-8"),
                       "netguard_rapport.csv", "text/csv")

with tab2:
    alerts = res.index[res["verdict"] != "normal"].tolist() or res.index.tolist()
    i = st.selectbox("Choisir une connexion (index)", alerts,
                     format_func=lambda k: f"#{k} — {res.loc[k, 'verdict']} ({res.loc[k, 'service']})")
    pos = res.index.get_loc(i)
    verdict = res.loc[i, "verdict"]
    cls = int(proba[pos].argmax())
    a, b = st.columns([1, 1.4])
    with a:
        st.markdown(f"### Verdict : **{verdict}**")
        st.write(f"Confiance du classifieur : **{proba[pos].max():.1%}**")
        st.write(f"Score d'anomalie : **{res.loc[i, 'score_anomalie']:.3f}** "
                 f"(seuil {-m['iso_threshold']:.3f})")
        key = verdict if verdict in ADVICE else "R2L"
        st.warning(ADVICE[key] if verdict in ADVICE else
                   "Comportement inhabituel non reconnu : isoler et analyser manuellement (possible attaque inédite).")
        st.plotly_chart(px.bar(x=CLASSES, y=proba[pos], color=CLASSES, color_discrete_map=COLORS,
                               title="Probabilités par classe")
                        .update_layout(showlegend=False, xaxis_title=None, yaxis_title=None),
                        width="stretch")
    with b:
        sv = np.array(get_explainer(m["classifier"]).shap_values(X[pos:pos + 1]))
        if sv.ndim == 3 and sv.shape[0] == len(CLASSES):
            contrib = sv[cls, 0]
        elif sv.ndim == 3:
            contrib = sv[0, :, cls]
        else:
            contrib = sv[0]
        top = np.argsort(np.abs(contrib))[::-1][:12]
        exp = pd.DataFrame({"variable": [m["feature_names"][k] for k in top],
                            "contribution": contrib[top]})
        exp["sens"] = np.where(exp["contribution"] > 0, f"pousse vers {CLASSES[cls]}", "pousse contre")
        st.plotly_chart(px.bar(exp[::-1], x="contribution", y="variable", orientation="h", color="sens",
                               color_discrete_sequence=["#d64545", "#2f6fd6"],
                               title=f"Pourquoi « {CLASSES[cls]} » ? (valeurs SHAP)")
                        .update_layout(yaxis_title=None, legend_title=None),
                        width="stretch")
    st.dataframe(res.loc[[i], FEATURES], width="stretch")

with tab3:
    st.markdown("Évaluation sur **KDDTest+** (22 544 connexions), qui contient "
                f"**{len(metrics['unseen_attack_types'])} types d'attaques absents de l'entraînement**.")
    rows = []
    for k, name in [("baseline", "XGBoost de référence"), ("netguard_classifier", "NetGuard (SMOTE + coûts)"),
                    ("netguard_hybrid", "NetGuard hybride (+ détecteur d'anomalies)")]:
        mm = metrics[k]
        rows.append({"Modèle": name, "F1 macro": mm["macro_f1"], "Exactitude": mm["accuracy"],
                     "Détection d'attaques": mm["attack_detection_rate"],
                     "Fausses alertes": mm["false_alarm_rate"],
                     "Rappel R2L": mm["per_class_recall"]["R2L"], "Rappel U2R": mm["per_class_recall"]["U2R"],
                     "Détection attaques inédites": metrics["unseen_attack_detection"][k]})
    st.dataframe(pd.DataFrame(rows).style.format({c: "{:.1%}" for c in rows[0] if c != "Modèle"}),
                 width="stretch", hide_index=True)
    c1, c2 = st.columns(2)
    c1.image(os.path.join(ART, "recall_comparison.png"))
    c2.image(os.path.join(ART, "confusion_matrix.png"))
    st.image(os.path.join(ART, "shap_importance.png"), width=650)

with tab4:
    st.markdown("""
**Problème.** Les systèmes de détection d'intrusions apprennent surtout le trafic normal et les attaques
massives (DoS). Les attaques rares mais critiques (accès distant R2L, élévation de privilèges U2R) et les
attaques **jamais vues** passent souvent inaperçues.

**Approche NetGuard.**
1. Prétraitement : log-transformation des compteurs, encodage one-hot du protocole, service et flag.
2. **SMOTE** sur les classes rares (R2L, U2R) + **pondération des coûts** dans XGBoost.
3. **Détecteur d'anomalies** (Isolation Forest) entraîné uniquement sur le trafic normal : il signale
   ce qui ne ressemble pas au normal, même si l'attaque est inconnue.
4. **Explicabilité SHAP** pour chaque alerte + recommandation de réponse pour l'analyste.

**Données.** NSL-KDD (Université du Nouveau-Brunswick), version corrigée de KDD'99.

**Limites.** NSL-KDD date de 2009 ; avant déploiement réel, ré-entraîner sur des flux récents
(CICIDS, UNSW-NB15 ou captures propres à l'organisation).
""")
