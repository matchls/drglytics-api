"""
Tests de régression sur build_dashboard_data().

OBJECTIF : geler le comportement ACTUEL du backend avant tout refactor.
Les valeurs ci-dessous (« golden values ») ont été capturées sur la save
d'exemple `player_save_example.json` (joueur « Gravn »). Si un changement de
code les modifie, c'est un signal — soit une régression à corriger, soit une
golden value à mettre à jour volontairement.

Le parseur GVAS (parse_save.py) est testé INDIRECTEMENT : la fixture vient d'un
JSON déjà parsé, donc on verrouille la sortie de stats_builder qui en dépend.

──────────────────────────────────────────────────────────────────────────────
MODE D'EMPLOI (mode apprentissage)
La 1ʳᵉ fonction (test_player_identity) est complète : sers-t'en de gabarit.
Les suivantes contiennent les golden values en commentaire et un « # TODO » :
remplace chaque `assert False, "TODO ..."` par la vraie assertion.
──────────────────────────────────────────────────────────────────────────────
"""

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# 1. IDENTITÉ DU JOUEUR — exemple COMPLET (gabarit à imiter)
# ─────────────────────────────────────────────────────────────────────────────

def test_player_identity(dashboard):
    """Le nom passé en argument et les perk points lus dans la save sont corrects."""
    player = dashboard["player"]
    assert player["name"] == "Gravn"
    assert player["perk_points"] == 87


# ─────────────────────────────────────────────────────────────────────────────
# 2. HERO STATS — totaux globaux mis en avant
#    Golden values capturées DEPUIS player_save_example.json (la fixture) :
#      MS_Killed_TotalEnemies     -> 51597          (entier)
#      MS_Completed_TotalMissions -> 307            (entier)
#      MS_TimePlayed              -> 579356.1133    (FLOAT, décimales !)
#      MS_DistanceTravelled       -> 151228510      (entier)
#      MS_Death_TotalDowns        -> 2179           (entier)
#      MS_Mined_TotalMinerals     -> 109587.3443    (FLOAT, décimales !)
#    Accès : dashboard["hero_stats"]["<asset_name>"]["total"]
#
#    ⚠️ PIÈGE FLOAT : deux totaux ne sont PAS des entiers. Pour eux, compare
#    avec pytest.approx (déjà importé en bas via `import pytest`) :
#        assert hero["MS_TimePlayed"]["total"] == pytest.approx(579356.1133)
#    (l'égalité exacte == 579356 échouerait sur ces deux-là).
# ─────────────────────────────────────────────────────────────────────────────

def test_hero_stats_totals(dashboard):
    hero = dashboard["hero_stats"]
    # Vérifie que les 6 stats héros attendues sont présentes :
    assert set(hero.keys()) == {
        "MS_Killed_TotalEnemies",
        "MS_Completed_TotalMissions",
        "MS_TimePlayed",
        "MS_DistanceTravelled",
        "MS_Death_TotalDowns",
        "MS_Mined_TotalMinerals",
    }
    # Totaux entiers : égalité exacte.
    assert hero["MS_Killed_TotalEnemies"]["total"] == 51597
    assert hero["MS_Completed_TotalMissions"]["total"] == 307
    assert hero["MS_DistanceTravelled"]["total"] == 151228510
    assert hero["MS_Death_TotalDowns"]["total"] == 2179
    # Totaux à décimales : comparaison "à un cheveu près" avec pytest.approx.
    assert hero["MS_TimePlayed"]["total"] == pytest.approx(579356.1133)
    assert hero["MS_Mined_TotalMinerals"]["total"] == pytest.approx(109587.3443)


# ─────────────────────────────────────────────────────────────────────────────
# 3. RÉSUMÉ PAR CLASSE
#    dashboard["classes"] est une LISTE de 4 dicts, dans l'ordre :
#      [Driller, Gunner, Engineer, Scout]   (constante CLASS_ORDER)
#    Golden values :
#                 missions_completed   kills
#      Driller          93            18433
#      Gunner           29            15625
#      Engineer         67            12365
#      Scout           118             5174
#    Chaque dict : {"name", "color", "missions_completed", "kills", ...}
# ─────────────────────────────────────────────────────────────────────────────

def test_classes_order_and_names(dashboard):
    classes = dashboard["classes"]
    assert len(classes) == 4
    # On extrait les noms dans l'ordre de la liste et on compare à l'ordre attendu.
    names = [c["name"] for c in classes]
    assert names == ["Driller", "Gunner", "Engineer", "Scout"]


def test_classes_missions_and_kills(dashboard):
    # Astuce : transformer la liste en dict indexé par nom rend les assertions lisibles.
    by_name = {c["name"]: c for c in dashboard["classes"]}
    # Missions complétées par classe.
    assert by_name["Driller"]["missions_completed"] == 93
    assert by_name["Gunner"]["missions_completed"] == 29
    assert by_name["Engineer"]["missions_completed"] == 67
    assert by_name["Scout"]["missions_completed"] == 118
    # Kills par classe.
    assert by_name["Driller"]["kills"] == 18433
    assert by_name["Gunner"]["kills"] == 15625
    assert by_name["Engineer"]["kills"] == 12365
    assert by_name["Scout"]["kills"] == 5174


# ─────────────────────────────────────────────────────────────────────────────
# 4. OVERCLOCKS
#    dashboard["overclocks"] = {
#       "forged_count": 0, "unforged_count": 0,
#       "forged": [], "unforged": [], "forged_by_dwarf": {Driller:[], ...}
#    }
#
#    ⚠️ LIMITATION CONNUE DE LA FIXTURE : player_save_example.json contient bien
#    97 entrées ForgedSchematics et 8 OwnedSchematics, MAIS ce sont des structs
#    Guid VIDES ({"_type":"Guid"} sans valeur). resolve_oc() les filtre car le
#    GUID est absent → les comptes RÉSOLUS tombent à 0. On verrouille donc 0 :
#    c'est le comportement réel de stats_builder sur cette fixture, et le test
#    protège resolve_oc contre un refactor qui changerait ce filtrage.
#    (Suivi : régénérer la fixture depuis le .sav pour des GUIDs réels.)
# ─────────────────────────────────────────────────────────────────────────────

def test_overclocks_counts(dashboard):
    ocs = dashboard["overclocks"]
    # Comptes résolus = 0 sur cette fixture (GUIDs vides, cf. note ci-dessus).
    assert ocs["forged_count"] == 0
    assert ocs["unforged_count"] == 0
    # Cohérence : le compte annoncé correspond à la longueur réelle des listes.
    assert len(ocs["forged"]) == ocs["forged_count"]
    assert len(ocs["unforged"]) == ocs["unforged_count"]


# ─────────────────────────────────────────────────────────────────────────────
# 5. INVARIANTS INTERNES (cohérence, pas juste des valeurs figées)
#    Ces tests survivent même si les golden values changent : ils vérifient une
#    RELATION qui doit toujours tenir.
# ─────────────────────────────────────────────────────────────────────────────

def test_invariant_missions_sum_equals_hero_total(dashboard):
    """Cohérence observée sur cette fixture : la somme des missions par classe
    égale le total héros 'Total Missions'. NB : ces deux valeurs viennent de
    stats sources distinctes — l'égalité n'est pas garantie par le code pour
    toute save, on la verrouille telle qu'observée sur player_save_example.json."""
    classes = dashboard["classes"]
    hero_total = dashboard["hero_stats"]["MS_Completed_TotalMissions"]["total"]
    sum_per_class = sum(c["missions_completed"] for c in classes)
    assert sum_per_class == hero_total


def test_invariant_forged_by_dwarf_sums_to_count(dashboard):
    """La somme des overclocks forgés par dwarf doit égaler forged_count."""
    ocs = dashboard["overclocks"]
    total_grouped = sum(len(group) for group in ocs["forged_by_dwarf"].values())
    assert total_grouped == ocs["forged_count"]
