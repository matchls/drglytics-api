"""
Fixtures partagées pour la suite de tests.

Analogie : une fixture, c'est la « mise en place » d'un cuisinier — on prépare
les ingrédients une fois, avant le service, pour que chaque plat (test) parte
de la même base propre.
"""
import json
from pathlib import Path

import pytest

from stats_builder import build_dashboard_data

# Racine du dépôt = dossier parent de tests/
REPO_ROOT = Path(__file__).resolve().parent.parent

# Pseudo de référence : c'est le joueur contenu dans la save d'exemple.
EXAMPLE_PLAYER_NAME = "Gravn"


@pytest.fixture(scope="session")
def raw_save() -> dict:
    """Le dictionnaire brut, tel que parse_save.py le produirait à partir du .sav.

    On part du JSON d'exemple déjà parsé (player_save_example.json) plutôt que
    d'un vrai .sav binaire : ça teste stats_builder sur une entrée stable et
    versionnée, sans dépendre d'un fichier de save présent sur le disque.
    """
    fixture_path = REPO_ROOT / "player_save_example.json"
    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def dashboard(raw_save) -> dict:
    """Le résultat de build_dashboard_data() — l'objet envoyé au frontend.

    C'est LA sortie qu'on verrouille : si un refactor de stats_builder change
    ces valeurs, les tests qui consomment cette fixture tomberont.
    """
    return build_dashboard_data(raw_save, player_name=EXAMPLE_PLAYER_NAME)
