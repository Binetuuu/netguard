# NetGuard

Détection d'intrusions réseau robuste aux attaques rares et inédites, avec une explication pour chaque alerte.

Projet présenté au **DataNova 2026 – Global Data-thon**, problème **DN-CY-01 : Network Intrusion Detection with Imbalanced Threat Data**.
Autrice : **Binetou Rassoul SEYE**

## Le problème
Dans le trafic réseau, les attaques les plus graves sont aussi les plus rares. Dans NSL-KDD, l'élévation de privilèges (U2R) représente 52 connexions sur 125 973. Un modèle classique apprend surtout le trafic normal et les dénis de service, et laisse passer ces attaques rares. Il rate aussi les attaques qu'il n'a jamais vues.

## L'approche
1. **Prétraitement** : log-transformation des compteurs, encodage one-hot du protocole, du service et du flag.
2. **Filet 1 : classifieur XGBoost** entraîné avec **SMOTE** (sur-échantillonnage de R2L et U2R) et une pondération des classes.
3. **Filet 2 : Isolation Forest** entraîné uniquement sur le trafic normal. Si le classifieur dit « normal » mais que la connexion est anormale (ou que la confiance est inférieure à 80 %), une alerte « suspecte » est levée.
4. **Explicabilité SHAP** pour chaque alerte, avec une action de réponse recommandée.

## Résultats (KDDTest+, 22 544 connexions, 17 types d'attaques inédits)

| Modèle | F1 macro | Détection des attaques | Fausses alertes | Rappel U2R | Attaques inédites |
|---|---|---|---|---|---|
| XGBoost de référence | 0,53 | 65,1 % | 2,9 % | 7,5 % | 35,9 % |
| NetGuard (SMOTE + coûts) | 0,62 | 67,1 % | 2,9 % | 28,4 % | 34,6 % |
| **NetGuard hybride** | **0,69** | **76,5 %** | 3,2 % | **43,3 %** | **62,7 %** |

Les chiffres exacts sont produits par `train.py` dans `artifacts/metrics.json`.

## Lancer le projet
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows  (source .venv/bin/activate sous Linux/macOS)
pip install -r requirements.txt

# (optionnel) ré-entraîner : télécharge d'abord les données
curl -L -o data/KDDTrain+.txt https://raw.githubusercontent.com/defcom17/NSL_KDD/master/KDDTrain+.txt
curl -L -o data/KDDTest+.txt  https://raw.githubusercontent.com/defcom17/NSL_KDD/master/KDDTest+.txt
python train.py

# application web
streamlit run app.py
```
Le modèle déjà entraîné (`artifacts/netguard_model.joblib`) et un échantillon de démonstration (`data/demo_traffic.csv`) sont inclus : l'application démarre sans ré-entraînement.

## Structure
| Fichier | Rôle |
|---|---|
| `netguard_core.py` | colonnes, familles d'attaques, prétraitement partagé |
| `train.py` | entraînement, évaluation, graphiques, sauvegarde du modèle |
| `app.py` | application Streamlit (tableau de bord, explication des alertes, performances) |
| `make_slides.py` | génération de la présentation à partir des métriques |

## Limites
- NSL-KDD date de 2009 : il faut ré-entraîner sur des flux récents (CICIDS, UNSW-NB15) avant un usage réel.
- U2R reste très rare : le résultat doit être confirmé sur davantage de données.
- La règle hybride augmente légèrement les fausses alertes (de 2,9 % à 3,2 %). Le seuil est réglable dans l'application.

## Données
NSL-KDD, Canadian Institute for Cybersecurity, University of New Brunswick.
