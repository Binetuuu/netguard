"""Shared preprocessing for NetGuard (NSL-KDD network intrusion detection)."""
import numpy as np
import pandas as pd

COLUMNS = [
    "duration", "protocol_type", "service", "flag", "src_bytes", "dst_bytes", "land",
    "wrong_fragment", "urgent", "hot", "num_failed_logins", "logged_in", "num_compromised",
    "root_shell", "su_attempted", "num_root", "num_file_creations", "num_shells",
    "num_access_files", "num_outbound_cmds", "is_host_login", "is_guest_login", "count",
    "srv_count", "serror_rate", "srv_serror_rate", "rerror_rate", "srv_rerror_rate",
    "same_srv_rate", "diff_srv_rate", "srv_diff_host_rate", "dst_host_count",
    "dst_host_srv_count", "dst_host_same_srv_rate", "dst_host_diff_srv_rate",
    "dst_host_same_src_port_rate", "dst_host_srv_diff_host_rate", "dst_host_serror_rate",
    "dst_host_srv_serror_rate", "dst_host_rerror_rate", "dst_host_srv_rerror_rate",
    "attack", "difficulty",
]
FEATURES = COLUMNS[:-2]
CATEGORICAL = ["protocol_type", "service", "flag"]
LOG_COLS = ["duration", "src_bytes", "dst_bytes", "count", "srv_count",
            "dst_host_count", "dst_host_srv_count", "hot", "num_compromised", "num_root"]
NUMERIC = [c for c in FEATURES if c not in CATEGORICAL]

CLASSES = ["normal", "DoS", "Probe", "R2L", "U2R"]

ATTACK_FAMILY = {
    "normal": "normal",
    # DoS
    "back": "DoS", "land": "DoS", "neptune": "DoS", "pod": "DoS", "smurf": "DoS",
    "teardrop": "DoS", "apache2": "DoS", "udpstorm": "DoS", "processtable": "DoS",
    "mailbomb": "DoS",
    # Probe
    "satan": "Probe", "ipsweep": "Probe", "nmap": "Probe", "portsweep": "Probe",
    "mscan": "Probe", "saint": "Probe",
    # R2L
    "guess_passwd": "R2L", "ftp_write": "R2L", "imap": "R2L", "phf": "R2L",
    "multihop": "R2L", "warezmaster": "R2L", "warezclient": "R2L", "spy": "R2L",
    "xlock": "R2L", "xsnoop": "R2L", "snmpguess": "R2L", "snmpgetattack": "R2L",
    "httptunnel": "R2L", "sendmail": "R2L", "named": "R2L", "worm": "R2L",
    # U2R
    "buffer_overflow": "U2R", "loadmodule": "U2R", "rootkit": "U2R", "perl": "U2R",
    "sqlattack": "U2R", "xterm": "U2R", "ps": "U2R",
}

ADVICE = {
    "normal": "Trafic légitime : aucune action requise.",
    "DoS": "Déni de service : limiter le débit (rate limiting), bloquer l'IP source, activer la protection SYN-flood.",
    "Probe": "Reconnaissance / scan : journaliser l'IP source, fermer les ports inutiles, surveiller les tentatives suivantes.",
    "R2L": "Accès distant non autorisé : vérifier les tentatives de connexion, forcer la rotation des mots de passe, activer le MFA.",
    "U2R": "Élévation de privilèges : isoler l'hôte immédiatement, auditer les comptes root et les binaires modifiés.",
}


def load_nsl_kdd(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, header=None, names=COLUMNS)
    df["family"] = df["attack"].map(ATTACK_FAMILY).fillna("R2L")
    return df


def transform_numeric(X: pd.DataFrame) -> pd.DataFrame:
    """log1p on heavy-tailed counters (used inside the sklearn pipeline)."""
    X = X.copy()
    for c in LOG_COLS:
        if c in X:
            X[c] = np.log1p(X[c].clip(lower=0))
    return X
