"""
DRG Dashboard — GUID Mapper
============================
Traduit les GUIDs bruts du save en noms lisibles, en s'appuyant sur :
  - guids.json       : overclocks, cosmétiques, skins (AnthonyMichaelTDM)
  - stat_guids.json  : stats de mission (extrait depuis les assets du jeu)

Analogie : c'est un annuaire téléphonique.
  Le save contient des "numéros" (GUIDs).
  Ce module fait la recherche et retourne le "nom" associé.
"""

import json
from pathlib import Path
from functools import lru_cache

# ── Chemins vers les fichiers de mapping ──────────────────────────────────────

_BASE = Path(__file__).parent

# ── Chargement paresseux (on lit les fichiers une seule fois) ─────────────────

@lru_cache(maxsize=1)
def _load_guids() -> dict:
    """Charge guids.json (overclocks, cosmétiques)."""
    path = _BASE / "guids.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_stat_guids() -> dict:
    """Charge stat_guids.json (stats de mission)."""
    path = _BASE / "stat_guids.json"
    if not path.exists():
        return {"stats": {}, "categories": {}}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── GUIDs des classes (hard-codés, stables dans le jeu) ──────────────────────

CLASS_GUIDS: dict[str, str] = {
    "30d8ea17d8fbba4c95306de9655c2f8c": "Scout",
    "9edd56f1eebcc5488d5b5e5b80b62db4": "Driller",
    "85ef626c65f1024a8dfeb5d0f3909d2e": "Engineer",
    "ae56e180fec0c44d96fa29c28366b97b": "Gunner",
}

# ── API publique ──────────────────────────────────────────────────────────────
#
# Note : les couleurs de classe sont gérées côté frontend (lib/types.ts,
# CLASS_COLORS), source unique. Le backend ne renvoie volontairement aucune
# couleur (préoccupation de présentation).

def get_class_name(class_guid: str) -> str:
    """Retourne le nom de la classe à partir de son GUID."""
    return CLASS_GUIDS.get(class_guid.lower(), f"Unknown ({class_guid[:8]}...)")


def get_stat_info(stat_guid: str) -> dict:
    """
    Retourne les infos d'une stat de mission à partir de son GUID.

    Retourne :
        {
            "name":     "Total Enemies Killed",
            "category": "MSC_Kills",
            "type":     "Integer"   # ou "Float"
        }
    """
    data = _load_stat_guids()
    stat = data["stats"].get(stat_guid.lower())
    if stat:
        return stat
    return {
        "name":     f"Unknown stat ({stat_guid[:8]}...)",
        "category": "Unknown",
        "type":     "Float",
        "asset_name": stat_guid,
    }


def get_overclock_info(oc_guid: str) -> dict | None:
    """
    Retourne les infos d'un overclock à partir de son GUID.

    Retourne :
        {
            "dwarf":  "Scout",
            "weapon": "Deepcore GK2",
            "name":   "Compact Ammo",
            "cost":   { "credits": 7250, "bismor": 125, ... }
        }
    ou None si inconnu.
    """
    guids = _load_guids()
    # guids.json utilise des GUIDs en majuscules sans tirets
    normalized = oc_guid.upper().replace("-", "")
    return guids.get("Weapons", {}).get(normalized)


def get_stat_category_name(category_key: str) -> str:
    """
    Traduit une clé de catégorie en label lisible.
    Ex: 'MSC_Kills' → 'Kills'
    """
    # Les fichiers MSC_* ont des titres peu utiles (identiques à la clé)
    # On mappe manuellement les catégories connues
    CATEGORY_LABELS = {
        "MSC_Kills":       "Kills",
        "MSC_Missions":    "Missions",
        "MSC_Characters":  "Classes",
        "MSC_Bioms":       "Biomes",
        "MSC_DeepDives":   "Deep Dives",
        "MSC_Mined":       "Mining",
        "MSC_Distance":    "Distance",
        "MSC_Time":        "Time",
        "MSC_Death":       "Deaths",
        "MSC_Drinkables":  "Bar",
        "MSC_Forging":     "Forging",
        "MSC_Warnings":    "Warnings",
        "MSC_Seasons":     "Seasons",
        "MSC_Assignments": "Assignments",
        "MSC_Purchased":   "Purchases",
    }
    return CATEGORY_LABELS.get(category_key, category_key.replace("MSC_", ""))


def get_all_stats() -> dict:
    """Retourne le mapping complet GUID → info stat."""
    return _load_stat_guids().get("stats", {})


# ── Debug / test ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Classes ===")
    for guid, name in CLASS_GUIDS.items():
        print(f"  {name}: {guid}")

    print("\n=== Test stat GUID ===")
    test_guids = [
        "51597a4e8c3b4f4a9c7e2d1f0a8b3c6d",  # fictif
        "c4897a0f90059c41a5e1b778fcf859af",  # MS_Completed_Driller
    ]
    for g in test_guids:
        info = get_stat_info(g)
        print(f"  {g[:16]}... → {info['name']} [{info['category']}]")

    print("\n=== Test overclock GUID ===")
    test_oc = "AF945B93A7B9D64CA6DD00683627BC80"
    info = get_overclock_info(test_oc)
    print(f"  {test_oc} → {info}")
