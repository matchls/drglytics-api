# DRG Dashboard — Backend

API Flask qui parse les fichiers de sauvegarde Deep Rock Galactic (`.sav`) et retourne les statistiques du joueur en JSON.

> **Analogie générale :** Ce backend est un guichet. Le joueur dépose son fichier `.sav` sur le comptoir, le guichet le déchiffre et lui remet une fiche résumé lisible. Rien n'est conservé côté serveur.

---

## Lancement rapide

```bash
# 1. Installer les dépendances
pip install -r requirements.txt

# 2. Lancer l'API
python api.py
# → http://localhost:5000
```

---

## Rôle dans l'architecture globale

Ce backend est un **microservice de parsing** : il fait une seule chose (lire un `.sav` binaire et retourner du JSON), mais il la fait bien. Toute la sécurité, l'authentification et l'écriture en base de données vivent dans le frontend Next.js, qui appelle ce backend en server-to-server.

```
Navigateur
    │
    │  upload du fichier .sav
    ▼
Next.js (app/api/upload/route.ts)
    │
    ├──► POST /api/parse  ← CE BACKEND (parsing uniquement)
    │        └──► retourne le JSON de stats
    │
    └──► Supabase (persistance leaderboard, côté Next.js)
```

---

## Fichiers du projet

```
drg_dashboard_backend/
├── api.py              ← Serveur Flask — endpoint POST /api/parse
├── parse_save.py       ← Parseur binaire GVAS (format Unreal Engine 4.27)
├── guid_mapper.py      ← Traduction des GUIDs en noms lisibles
├── stats_builder.py    ← Construction du JSON final pour le frontend
├── guids.json          ← Mapping overclocks / cosmétiques (source : AnthonyMichaelTDM)
├── stat_guids.json     ← Mapping stats de mission (extrait via FModel)
├── tests/
│   ├── conftest.py     ← Fixtures partagées (fixture dashboard = sortie de build_dashboard_data)
│   └── test_stats_builder.py ← Tests de régression sur les golden values
└── requirements.txt    ← Dépendances Python
```

---

## Pipeline de données

Les données traversent 4 couches dans l'ordre :

```
fichier.sav (binaire GVAS)
        │
        ▼  parse_save.py — l'archéologue
        │  Lit les octets bruts, produit un dict Python.
        │  Chaque champ GVAS a la forme : [nom][type][taille][données]
        │  Ex: "PerkPoints" IntProperty 4 → 87
        │
        ▼  guid_mapper.py — l'annuaire
        │  Traduit les GUIDs (codes internes du jeu) en noms lisibles.
        │  Ex: "ae56e180..." → "Gunner"
        │      "f803c36f..." → "MS_DistanceTravelled"
        │
        ▼  stats_builder.py — le conservateur de musée
        │  Regroupe, agrège et formate les données.
        │  Ex: liste plate de compteurs → totaux par classe
        │
        ▼  api.py — le guichet
           Sérialise en JSON, applique sécurité et rate limiting.
           Retourne {"ok": true, "data": {...}}
```

---

## Endpoints

### `POST /api/parse`

Parse un fichier `.sav` et retourne les stats du joueur.

**Paramètres (form-data) :**

| Champ | Type | Description |
|---|---|---|
| `file` | Fichier `.sav` | Fichier de sauvegarde DRG (max 5 MB) |
| `player_name` | Texte | Pseudo du joueur (max 64 caractères) |

**Réponse succès (200) :**
```json
{
  "ok": true,
  "data": {
    "player": { "name": "Gravn", "perk_points": 87 },
    "hero_stats": {
      "MS_Killed_TotalEnemies": { "label": "Total Enemies Killed", "total": 51597, "by_class": {...} }
    },
    "classes": [
      { "name": "Driller", "missions_completed": 93, "kills": 18433, "time_played_s": 0, ... }
    ],
    "mission_stats": { "MS_DistanceTravelled": { "name": "Distance Travelled", "total": 151228510, "by_class": {...} } },
    "overclocks": { "forged_count": 97, "forged": [...], "forged_by_dwarf": {...} }
  }
}
```

**Réponse erreur (4xx / 5xx) :**
```json
{ "ok": false, "error": "message d'erreur lisible" }
```

### `GET /api/health`

Health check — utile pour les monitors de Railway.

```json
{ "ok": true, "service": "drg-dashboard-api" }
```

---

## Format GVAS — comment le parseur lit le binaire

Les fichiers `.sav` sont au format **GVAS** (Unreal Engine). Ce n'est pas du JSON ni du texte : c'est un dictionnaire imbriqué encodé en octets bruts.

### Structure d'un champ

Chaque propriété a la forme :

```
[nom_str] [type_str] [taille i64] [payload]
```

Par exemple, `PerkPoints = 87` est encodé comme :

```
"PerkPoints"  "IntProperty"  4  <87 en little-endian>
```

### Types supportés

| Type Unreal | Python produit | Particularité |
|---|---|---|
| `IntProperty` | `int` | tag(1) + i32(4) |
| `FloatProperty` | `float` | tag(1) + f32(4) |
| `BoolProperty` | `bool` | tag = valeur + 1 byte padding |
| `StrProperty` | `str` | UTF-8 ou UTF-16LE si longueur < 0 |
| `EnumProperty` | `str` | précédé du nom du type d'enum |
| `StructProperty` | `dict` | contient d'autres props (récursif) |
| `ArrayProperty` | `list` | peut contenir des structs (récursif) |
| `MapProperty` / `SetProperty` | *(skippés)* | non encore parsés |

### Sémantique de la taille

- **Scalaires** (`Int`, `Float`, `Bool`, `Str`) : `size` = données seules, tag exclu
- **StructProperty** : `size` = octets des sous-props après `struct_type_str + 17 bytes` (GUID + tag)
- **ArrayProperty** : `size` = payload − len(itype_str) − 1 (tag)

### Garde-fous anti-abus

Un `.sav` forgé pourrait annoncer un tableau de milliards d'items ou imbriquer des structs à l'infini. Deux limites protègent le serveur :

```python
MAX_DEPTH = 100              # profondeur max d'imbrication (anti-récursion)
count > len(self.d) → raise  # count tableau borné au nombre d'octets disponibles
```

---

## Sécurité de l'API

| Mécanisme | Valeur | Raison |
|---|---|---|
| Rate limiting général | 60 req/heure | protéger les ressources serveur |
| Rate limiting `/api/parse` | 10 req/minute | le parsing est coûteux en CPU |
| Taille max fichier | 5 MB | un `.sav` DRG réel fait ~500 KB |
| CORS restreint | `ALLOWED_ORIGINS` env | seul le domaine frontend autorisé |
| `ProxyFix` | `x_for=1` | rate limiting par IP réelle derrière Railway |
| Messages d'erreur vagues | `"Could not parse..."` | ne pas aider à forger des `.sav` malveillants |

---

## Tests

Les tests verrouillent les **golden values** produites par `build_dashboard_data()` sur la fixture `player_save_example.json` (joueur "Gravn"). Si un refactor modifie ces valeurs, les tests tombent — c'est le signal qu'il faut valider le changement.

```bash
pytest tests/
```

---

## Commandes utiles

```bash
# Lancer l'API en local
python api.py

# Tester le parseur directement sur un fichier .sav
python parse_save.py Saved/SaveGames/<steam_id>_Player.sav

# Tester le stats_builder en standalone
python stats_builder.py

# Lancer les tests
pytest tests/
```

---

## Notes

- Ne pas modifier les fichiers dans `Saved/` — ce sont de vraies saves de jeu
- Le parseur `parse_save.py` est fait maison (reverse engineering) — ne pas le réécrire sans comprendre le format GVAS
- Le mapping des GUIDs vient du projet open-source [AnthonyMichaelTDM/drg-completionist](https://github.com/AnthonyMichaelTDM/drg-completionist)
- Les couleurs de classe sont gérées **côté frontend uniquement** — le backend ne renvoie pas de couleurs (séparation des préoccupations)
