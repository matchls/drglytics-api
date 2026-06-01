"""
DRG Dashboard — Stats Builder
==============================
Transforme le dictionnaire brut produit par parse_save.py en un objet
JSON structuré, lisible, prêt à être consommé par le frontend React.

Analogie : parse_save.py est l'archéologue qui extrait les artefacts du sol.
stats_builder.py est le conservateur de musée qui les nettoie, les étiquette,
et les dispose dans des vitrines thématiques.
"""

from guid_mapper import (
    get_class_name,
    get_stat_info,
    get_overclock_info,
    get_stat_category_name,
    CLASS_GUIDS,
)

# ── Constantes ────────────────────────────────────────────────────────────────

# Ordre d'affichage des classes dans le dashboard
CLASS_ORDER = ["Driller", "Gunner", "Engineer", "Scout"]

# Stats à mettre en avant dans la section "héros" du dashboard
HERO_STAT_ASSETS = {
    "MS_Killed_TotalEnemies": "Total Enemies Killed",
    "MS_Completed_TotalMissions": "Total Missions",
    "MS_TimePlayed": "Time Played (s)",
    "MS_DistanceTravelled": "Distance Travelled (cm)",
    "MS_Death_TotalDowns": "Total Downs",
    "MS_Mined_TotalMinerals": "Total Minerals Mined",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

import re

def _format_stat_name(asset_name: str) -> str:
    """
    Convertit un nom d'asset brut en texte lisible.
    Ex: "MS_Completed_DeepScan" → "Deep Scan"
        "MS_Killed_TotalEnemies" → "Total Enemies"
    Analogie : c'est un traducteur qui enlève le jargon technique
    et ajoute des espaces là où les mots sont collés.
    """
    # Enlever le préfixe "MS_MotCle_"
    name = re.sub(r'^MS_[^_]+_', '', asset_name)
    # Enlever le préfixe "MS_" seul (ex: MS_TimePlayed)
    name = re.sub(r'^MS_', '', name)
    # Ajouter un espace avant chaque majuscule qui suit une minuscule
    # "DeepScan" → "Deep Scan"
    name = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', name)
    return name


def _build_mission_stats(counters: list) -> dict:
    """
    Prend la liste brute des MissionStatCounters et retourne :
    {
        "by_stat": {
            "MS_Killed_TotalEnemies": {
                "name": "Total Enemies Killed",
                "category": "Kills",
                "total": 51597,
                "by_class": {
                    "Driller": 18433,
                    "Gunner": 15625,
                    ...
                }
            },
            ...
        }
    }
    """
    # Agréger les valeurs : stat_guid → class_guid → valeur
    raw: dict[str, dict[str, float]] = {}
    for counter in counters:
        stat_guid = counter["MissionStatID"]
        class_guid = counter["PlayerClassID"]
        value = counter["Value"]

        if stat_guid not in raw:
            raw[stat_guid] = {}
        raw[stat_guid][class_guid] = value

    # Stats avec unités spéciales
    UNIT_MAP = {
        "MS_DistanceTravelled": "cm",
        "MS_TimePlayed": "s",
    }

    # Construire la structure finale
    by_stat = {}
    for stat_guid, class_values in raw.items():
        info = get_stat_info(stat_guid)

        # Ignorer les stats inconnues (GUID absent du stat_guids.json)
        if info["category"] == "Unknown":
            continue

        # Résoudre les GUIDs de classes en noms
        by_class = {}
        total = 0.0
        for class_guid, value in class_values.items():
            class_name = get_class_name(class_guid)
            by_class[class_name] = value
            total += value

        asset_name = info["asset_name"]
        by_stat[asset_name] = {
            "guid": stat_guid,
            "name": _format_stat_name(asset_name),
            "category": get_stat_category_name(info["category"]),
            "category_key": info["category"],
            "type": info["type"],
            "unit": UNIT_MAP.get(asset_name, ""),
            "total": total,
            "by_class": by_class,
        }

    return by_stat


def _build_overclocks(schematic_save: dict) -> dict:
    """
    Retourne les overclocks forgés et non forgés avec leurs infos lisibles.
    {
        "forged": [
            { "guid": "...", "dwarf": "Scout", "weapon": "GK2", "name": "Compact Ammo" },
            ...
        ],
        "unforged": [...],
        "forged_count": 97,
        "total_available": 160
    }
    """
    forged_guids = schematic_save.get("ForgedSchematics", [])
    owned_guids = schematic_save.get("OwnedSchematics", [])

    def resolve_oc(guid_obj) -> dict | None:
        # Le parseur peut retourner soit un str soit {"_type": "Guid", ...}
        if isinstance(guid_obj, str):
            guid = guid_obj
        elif isinstance(guid_obj, dict):
            # Essayons d'extraire le GUID si disponible
            guid = guid_obj.get("guid") or guid_obj.get("value", "")
        else:
            return None

        if not guid:
            return None

        info = get_overclock_info(guid)
        if info:
            return {
                "guid": guid,
                "dwarf": info.get("dwarf", "Unknown"),
                "weapon": info.get("weapon", "Unknown"),
                "name": info.get("name", "Unknown"),
                "cost": info.get("cost", {}),
            }
        return {"guid": guid, "dwarf": "Unknown", "weapon": "Unknown", "name": guid[:8] + "..."}

    forged = [r for g in forged_guids if (r := resolve_oc(g)) is not None]
    unforged = [r for g in owned_guids if (r := resolve_oc(g)) is not None]

    # Grouper les forgés par classe pour le dashboard
    by_dwarf: dict[str, list] = {name: [] for name in CLASS_ORDER}
    for oc in forged:
        dwarf = oc["dwarf"]
        if dwarf in by_dwarf:
            by_dwarf[dwarf].append(oc)
        else:
            by_dwarf.setdefault(dwarf, []).append(oc)

    return {
        "forged": forged,
        "forged_by_dwarf": by_dwarf,
        "unforged": unforged,
        "forged_count": len(forged),
        "unforged_count": len(unforged),
    }


def _build_class_summary(mission_stats: dict) -> list:
    """
    Construit un résumé par classe à partir des stats de mission.
    [
        {
            "name": "Driller",
            "missions_completed": 525,
            "kills": 18433,
            ...
        },
        ...
    ]
    """
    # Mapping asset_name → clé dans le résumé
    STAT_MAP = {
        "MS_Completed_Driller":   ("Driller",  "missions_completed"),
        "MS_Completed_Engineer":  ("Engineer", "missions_completed"),
        "MS_Completed_Gunner":    ("Gunner",   "missions_completed"),
        "MS_Completed_Scout":     ("Scout",    "missions_completed"),
    }

    classes = {
        name: {
            "name": name,
            "missions_completed": 0,
            "kills": 0,
            "time_played_s": 0,
            "distance_cm": 0,
            "downs": 0,
        }
        for name in CLASS_ORDER
    }

    # Remplir depuis les stats globales "by_class"
    for asset_name, stat in mission_stats.items():
        by_class = stat.get("by_class", {})
        for class_name, value in by_class.items():
            if class_name not in classes:
                continue
            key = asset_name
            if key == "MS_Killed_TotalEnemies":
                classes[class_name]["kills"] += value
            elif key == "MS_TimePlayed":
                classes[class_name]["time_played_s"] += value
            elif key == "MS_DistanceTravelled":
                classes[class_name]["distance_cm"] += value
            elif key == "MS_Death_TotalDowns":
                classes[class_name]["downs"] += value

    # Missions complétées par classe (stats dédiées)
    for asset_name, (class_name, field) in STAT_MAP.items():
        if asset_name in mission_stats:
            val = mission_stats[asset_name].get("total", 0)
            if class_name in classes:
                classes[class_name][field] = val

    return [classes[name] for name in CLASS_ORDER]


# ── Point d'entrée principal ──────────────────────────────────────────────────

def build_dashboard_data(save_data: dict, player_name: str) -> dict:
    """
    Construit l'objet complet envoyé au frontend.

    Args:
        save_data:   dictionnaire produit par parse_save.py
        player_name: pseudo entré par le joueur au moment de l'upload

    Returns:
        Un dict JSON-sérialisable avec toutes les stats du dashboard.
    """
    # 1. Stats de mission
    counters = save_data.get("MissionStatsSave", {}).get("Counters", [])
    mission_stats = _build_mission_stats(counters)

    # 2. Stats héros (globales, mises en avant)
    hero_stats = {}
    for asset_name, label in HERO_STAT_ASSETS.items():
        if asset_name in mission_stats:
            hero_stats[asset_name] = {
                "label": label,
                "total": mission_stats[asset_name]["total"],
                "by_class": mission_stats[asset_name]["by_class"],
            }

    # 3. Résumé par classe
    class_summary = _build_class_summary(mission_stats)

    # 4. Overclocks
    overclocks = _build_overclocks(save_data.get("SchematicSave", {}))

    # 5. Infos générales du joueur
    perk_points = save_data.get("PerkPoints", 0)

    return {
        "player": {
            "name": player_name,
            "perk_points": perk_points,
        },
        "hero_stats": hero_stats,
        "classes": class_summary,
        "mission_stats": mission_stats,
        "overclocks": overclocks,
    }


# ── Test standalone ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    from pathlib import Path
    from parse_save import parse_gvas

    save_path = Path(__file__).parent / "Saved/SaveGames/76561197983653885_Player.sav"
    if not save_path.exists():
        # Fallback sur le JSON d'exemple
        with open(Path(__file__).parent / "player_save_example.json", encoding="utf-8") as f:
            raw = json.load(f)
    else:
        raw = parse_gvas(str(save_path))

    result = build_dashboard_data(raw, player_name="Gravn")

    print("=== Joueur ===")
    print(f"  Nom : {result['player']['name']}")
    print(f"  Perk points : {result['player']['perk_points']}")

    print("\n=== Stats héros ===")
    for key, stat in result["hero_stats"].items():
        print(f"  {stat['label']} : {stat['total']:,.0f}")

    print("\n=== Résumé par classe ===")
    for cls in result["classes"]:
        print(f"  {cls['name']}: {cls['missions_completed']} missions | {cls['kills']:,.0f} kills | {cls['time_played_s']/3600:.0f}h")

    print("\n=== Overclocks ===")
    print(f"  Forgés : {result['overclocks']['forged_count']}")
    print(f"  Non forgés : {result['overclocks']['unforged_count']}")
    for dwarf, ocs in result["overclocks"]["forged_by_dwarf"].items():
        print(f"  {dwarf}: {len(ocs)} overclocks forgés")
