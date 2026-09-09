"""Génère les jeux de données synthétiques de DataGuard.

Les fichiers produits reprennent exactement les 47 colonnes du fichier réel
(`data/sample/reference_schema.json`), afin que la même configuration de dataset
s'applique aux fichiers de test et à la source réelle. Chaque fichier dégradé ne
porte qu'une seule famille d'anomalie, pour qu'un test échoué désigne un seul
contrôle.

Déterminisme : à graine fixe et à `--now` identique, deux exécutions produisent
des fichiers octet pour octet identiques. `--now` existe parce que la fraîcheur
est une notion relative : sans lui, `clean.csv` deviendrait périmé au fil des
jours et le contrôle de fraîcheur se mettrait à échouer tout seul.

Usage :
    python scripts/generate_samples.py
    python scripts/generate_samples.py --out data/sample --now 2026-09-09T12:00:00Z
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

SEED = 42
ROWS = 1000

COLUMNS: list[str] = [
    "id", "latitude", "longitude", "Code postal", "pop", "Adresse", "Ville",
    "horaires", "services", "prix", "rupture", "geom",
    "Prix Gazole mis à jour le", "Prix Gazole",
    "Prix SP95 mis à jour le", "Prix SP95",
    "Prix E85 mis à jour le", "Prix E85",
    "Prix GPLc mis à jour le", "Prix GPLc",
    "Prix E10 mis à jour le", "Prix E10",
    "Prix SP98 mis à jour le", "Prix SP98",
    "Début rupture e10 (si temporaire)", "Type rupture e10",
    "Début rupture sp98 (si temporaire)", "Type rupture sp98",
    "Début rupture sp95 (si temporaire)", "Type rupture sp95",
    "Début rupture e85 (si temporaire)", "Type rupture e85",
    "Début rupture GPLc (si temporaire)", "Type rupture GPLc",
    "Début rupture gazole (si temporaire)", "Type rupture gazole",
    "Carburants disponibles", "Carburants indisponibles",
    "Carburants en rupture temporaire", "Carburants en rupture definitive",
    "Automate 24-24 (oui/non)", "Services proposés",
    "Département", "code_departement", "Région", "code_region",
    "horaires détaillés",
]

# Taux de valeurs nulles du fichier propre, par carburant. Ils reproduisent la
# réalité (tous les carburants ne sont pas distribués partout) et restent sous
# les seuils d'alerte de la configuration.
FUEL_NULL_RATE = {
    "Gazole": 0.03, "SP95": 0.70, "E85": 0.60,
    "GPLc": 0.85, "E10": 0.26, "SP98": 0.27,
}
FUEL_PRICE_BAND = {
    "Gazole": (1.99, 2.80), "SP95": (1.55, 2.74), "E85": (0.78, 2.24),
    "GPLc": (0.83, 2.19), "E10": (1.88, 2.73), "SP98": (1.98, 2.87),
}
FUEL_RUPTURE_KEY = {
    "Gazole": "gazole", "SP95": "sp95", "E85": "e85",
    "GPLc": "GPLc", "E10": "e10", "SP98": "sp98",
}

DEPARTEMENTS = [
    ("01", "Ain", "84", "Auvergne-Rhône-Alpes"),
    ("06", "Alpes-Maritimes", "93", "Provence-Alpes-Côte d'Azur"),
    ("13", "Bouches-du-Rhône", "93", "Provence-Alpes-Côte d'Azur"),
    ("29", "Finistère", "53", "Bretagne"),
    ("31", "Haute-Garonne", "76", "Occitanie"),
    ("33", "Gironde", "75", "Nouvelle-Aquitaine"),
    ("59", "Nord", "32", "Hauts-de-France"),
    ("69", "Rhône", "84", "Auvergne-Rhône-Alpes"),
    ("75", "Paris", "11", "Île-de-France"),
    ("89", "Yonne", "27", "Bourgogne-Franche-Comté"),
]
VILLES = [
    "Bourg-en-Bresse", "Nice", "Marseille", "Brest", "Toulouse",
    "Bordeaux", "Lille", "Lyon", "Paris", "Sens",
]
VOIES = ["ROUTE DE MAILLOT", "AVENUE DE LA GARE", "RUE DU MOULIN",
         "BOULEVARD VICTOR HUGO", "ZONE COMMERCIALE NORD", "CHEMIN DES VIGNES"]
SERVICES = ["Toilettes publiques", "Boutique alimentaire", "Station de gonflage",
            "Lavage automatique", "Restauration à emporter", "DAB (Distributeur automatique de billets)"]


def _iso(ts: datetime) -> str:
    """Format des dates de la source : ISO 8601 avec décalage horaire."""
    return ts.astimezone(timezone(timedelta(hours=-4))).isoformat()


def build_clean(now: datetime, rows: int = ROWS) -> pd.DataFrame:
    """Construit le jeu de données propre : aucun contrôle ne doit lever d'alerte."""
    rng = random.Random(SEED)
    data: dict[str, list] = {c: [] for c in COLUMNS}

    for i in range(rows):
        dep_code, dep_nom, reg_code, reg_nom = DEPARTEMENTS[i % len(DEPARTEMENTS)]
        ville = VILLES[i % len(VILLES)]

        # Coordonnées en degrés décimaux × 100000, comme dans la source.
        lat = rng.randint(4_200_000, 5_100_000)
        lon = rng.randint(-450_000, 940_000)

        data["id"].append(f"{dep_code}{i:06d}")
        data["latitude"].append(str(lat))
        data["longitude"].append(str(lon))
        data["Code postal"].append(f"{dep_code}{rng.randint(0, 999):03d}")
        data["pop"].append("A" if i % 20 == 0 else "R")
        data["Adresse"].append(f"{rng.randint(1, 250)} {rng.choice(VOIES)}")
        data["Ville"].append(ville)
        data["horaires"].append(
            '{"@automate-24-24": "", "jour": [{"@id": "1", "@nom": "Lundi", "@ferme": ""}]}'
        )
        chosen = rng.sample(SERVICES, rng.randint(1, 3))
        data["services"].append(json.dumps({"service": chosen}, ensure_ascii=False))
        data["geom"].append(f"{lat / 100000:.6f}, {lon / 100000:.6f}")
        data["Automate 24-24 (oui/non)"].append("Oui" if i % 2 == 0 else "Non")
        data["Services proposés"].append(",".join(chosen))
        data["Département"].append(dep_nom)
        data["code_departement"].append(dep_code)
        data["Région"].append(reg_nom)
        data["code_region"].append(reg_code)
        data["horaires détaillés"].append("Lundi 08.00-20.00, Mardi 08.00-20.00")

        dispo, indispo, rupt_temp, rupt_def = [], [], [], []
        prix_detail = []

        for fuel, null_rate in FUEL_NULL_RATE.items():
            lo, hi = FUEL_PRICE_BAND[fuel]
            key = FUEL_RUPTURE_KEY[fuel]
            sold = rng.random() >= null_rate

            if sold:
                price = round(rng.uniform(lo, hi), 3)
                # Mise à jour entre 15 minutes et 12 heures avant `now` : récent,
                # mais jamais dans le futur (le contrôle de cohérence l'interdit).
                maj = now - timedelta(minutes=rng.randint(15, 720))
                data[f"Prix {fuel}"].append(f"{price:.3f}")
                data[f"Prix {fuel} mis à jour le"].append(_iso(maj))
                dispo.append(fuel)
                prix_detail.append({"@nom": fuel, "@valeur": f"{price:.3f}"})
            else:
                data[f"Prix {fuel}"].append(None)
                data[f"Prix {fuel} mis à jour le"].append(None)
                indispo.append(fuel)

            # Rupture : renseignée pour une partie des carburants non distribués.
            if not sold and rng.random() < 0.5:
                temporaire = rng.random() < 0.3
                debut = now - timedelta(days=rng.randint(1, 900))
                data[f"Début rupture {key} (si temporaire)"].append(_iso(debut))
                data[f"Type rupture {key}"].append("temporaire" if temporaire else "definitive")
                (rupt_temp if temporaire else rupt_def).append(fuel)
            else:
                data[f"Début rupture {key} (si temporaire)"].append(None)
                data[f"Type rupture {key}"].append(None)

        data["prix"].append(json.dumps(prix_detail, ensure_ascii=False) if prix_detail else None)
        data["rupture"].append(
            json.dumps([{"@nom": f} for f in rupt_temp + rupt_def], ensure_ascii=False)
            if (rupt_temp or rupt_def) else None
        )
        data["Carburants disponibles"].append(",".join(dispo) if dispo else None)
        data["Carburants indisponibles"].append(",".join(indispo) if indispo else None)
        data["Carburants en rupture temporaire"].append(";".join(rupt_temp) if rupt_temp else None)
        data["Carburants en rupture definitive"].append(";".join(rupt_def) if rupt_def else None)

    return pd.DataFrame(data, columns=COLUMNS)


# --------------------------------------------------------------------------
# Variantes dégradées. Chacune part du fichier propre et n'introduit qu'une
# seule famille d'anomalie.
# --------------------------------------------------------------------------

def v_nulls_warning(df: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Ville vidée sur 3 % des lignes : seuil d'alerte 2 %, seuil d'échec 5 %."""
    df = df.copy()
    df.loc[df.index[:30], "Ville"] = None
    return df


def v_nulls_failed(df: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Prix Gazole vidé sur 50 % des lignes : seuil d'échec 40 %."""
    df = df.copy()
    idx = df.index[:500]
    df.loc[idx, "Prix Gazole"] = None
    df.loc[idx, "Prix Gazole mis à jour le"] = None
    return df


def v_duplicates_warning(df: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Un identifiant dupliqué, soit 0,1 % des lignes."""
    df = df.copy()
    df.loc[df.index[500], "id"] = df.loc[df.index[0], "id"]
    return df


def v_duplicates_failed(df: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Trente identifiants dupliqués, soit 3 % des lignes."""
    df = df.copy()
    for offset in range(30):
        df.loc[df.index[500 + offset], "id"] = df.loc[df.index[offset], "id"]
    return df


def v_types_failed(df: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Vingt-cinq valeurs non numériques dans Prix Gazole, soit 2,5 %."""
    df = df.copy()
    df.loc[df.index[:25], "Prix Gazole"] = "n/a"
    return df


def v_ranges_warning(df: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Huit valeurs hors bornes (0,8 %) : sous le seuil d'échec de 1 %."""
    df = df.copy()
    df.loc[df.index[:5], "Prix Gazole"] = "0.000"
    df.loc[df.index[5:8], "latitude"] = "9999999"
    return df


def v_ranges_failed(df: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Cent cinquante prix aberrants à 12,50 €, soit 15 %."""
    df = df.copy()
    df.loc[df.index[:150], "Prix Gazole"] = "12.500"
    return df


def v_stale(df: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Toutes les dates de mise à jour reculées de dix jours."""
    df = df.copy()
    for fuel in FUEL_NULL_RATE:
        col = f"Prix {fuel} mis à jour le"
        df[col] = df[col].map(
            lambda v: _iso(datetime.fromisoformat(v) - timedelta(days=10)) if pd.notna(v) else v
        )
    return df


def v_schema_added(df: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Colonne supplémentaire absente du schéma de référence."""
    df = df.copy()
    df["services_v2"] = "non renseigné"
    return df


def v_schema_removed(df: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Colonne Prix GPLc supprimée."""
    return df.drop(columns=["Prix GPLc"])


def v_schema_renamed(df: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Colonne Prix SP95 renommée."""
    return df.rename(columns={"Prix SP95": "Prix sans-plomb 95"})


def v_schema_type_changed(df: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Latitude écrite avec une virgule décimale : le type observé devient du texte."""
    df = df.copy()
    df["latitude"] = df["latitude"].map(lambda v: f"{int(v) / 100000:.5f}".replace(".", ","))
    return df


def v_volume_warning(df: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """850 lignes, soit une baisse de 15 %."""
    return df.iloc[:850].copy()


def v_volume_failed(df: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """300 lignes, soit une baisse de 70 %."""
    return df.iloc[:300].copy()


def v_empty(df: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """En-tête seul : l'ingestion doit échouer proprement."""
    return df.iloc[:0].copy()


def v_consistency(df: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Huit dates de mise à jour placées deux jours dans le futur, soit 0,8 %."""
    df = df.copy()
    col = "Prix Gazole mis à jour le"
    future = _iso(now + timedelta(days=2))
    filled = df.index[df[col].notna()][:8]
    df.loc[filled, col] = future
    return df


VARIANTS = {
    "nulls_warning": v_nulls_warning,
    "nulls_failed": v_nulls_failed,
    "duplicates_warning": v_duplicates_warning,
    "duplicates_failed": v_duplicates_failed,
    "types_failed": v_types_failed,
    "ranges_warning": v_ranges_warning,
    "ranges_failed": v_ranges_failed,
    "stale": v_stale,
    "schema_added": v_schema_added,
    "schema_removed": v_schema_removed,
    "schema_renamed": v_schema_renamed,
    "schema_type_changed": v_schema_type_changed,
    "volume_warning": v_volume_warning,
    "volume_failed": v_volume_failed,
    "empty": v_empty,
    "consistency": v_consistency,
}


def write_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, sep=";", index=False, encoding="utf-8-sig",
              lineterminator="\r\n", na_rep="")


def generate_all(out_dir: Path, now: datetime) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    clean = build_clean(now)
    written = {"clean": out_dir / "clean.csv"}
    write_csv(clean, written["clean"])
    for name, fn in VARIANTS.items():
        path = out_dir / f"{name}.csv"
        write_csv(fn(clean, now), path)
        written[name] = path
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("data/sample"))
    parser.add_argument(
        "--now", type=str, default=None,
        help="Instant de référence ISO 8601 (défaut : maintenant, UTC). "
             "À figer pour obtenir des fichiers reproductibles.",
    )
    args = parser.parse_args()

    now = (
        datetime.fromisoformat(args.now.replace("Z", "+00:00"))
        if args.now else datetime.now(timezone.utc)
    )
    written = generate_all(args.out, now)
    for name, path in written.items():
        rows = sum(1 for _ in path.open(encoding="utf-8-sig")) - 1
        print(f"{name:24} {rows:>5} lignes  {path}")
    print(f"\n{len(written)} fichiers écrits dans {args.out} (référence : {now.isoformat()})")


if __name__ == "__main__":
    main()
