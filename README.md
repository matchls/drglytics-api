# DRG Dashboard — Backend

API Flask qui parse les fichiers de sauvegarde Deep Rock Galactic (`.sav`) et retourne les statistiques du joueur en JSON.

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

## Architecture

```
drg_dashboard_backend/
├── api.py              ← Serveur Flask — endpoint POST /api/parse
├── parse_save.py       ← Parseur binaire GVAS (format Unreal Engine 4.27)
├── guid_mapper.py      ← Traduction des GUIDs en noms lisibles
├── stats_builder.py    ← Construction du JSON final pour le frontend
├── guids.json          ← Mapping overclocks / cosmétiques (source : AnthonyMichaelTDM)
├── stat_guids.json     ← Mapping stats de mission (extrait via FModel)
└── requirements.txt    ← Dépendances Python (flask, flask-cors)
```

---

## Endpoints

### `POST /api/parse`

Parse un fichier `.sav` et retourne les stats du joueur.

**Paramètres (form-data) :**

| Champ | Type | Description |
|---|---|---|
| `file` | Fichier `.sav` | Fichier de sauvegarde DRG |
| `player_name` | Texte | Pseudo du joueur (max 64 caractères) |

**Réponse succès (200) :**
```json
{
  "ok": true,
  "data": {
    "player": { "name": "..." },
    "hero_stats": { ... },
    "classes": [ ... ],
    "overclocks": [ ... ],
    "mission_stats": { ... }
  }
}
```

**Réponse erreur (4xx / 5xx) :**
```json
{
  "ok": false,
  "error": "message d'erreur lisible"
}
```

### `GET /api/health`

Health check — vérifie que l'API est en ligne.

```json
{ "ok": true, "service": "drg-dashboard-api" }
```

---

## Flux de données

```
Fichier .sav (binaire GVAS)
        ↓
  parse_save.py       → parse le binaire, retourne un dict Python brut
        ↓
  guid_mapper.py      → traduit les GUIDs en noms lisibles (overclocks, stats...)
        ↓
  stats_builder.py    → assemble et formate les données pour le frontend
        ↓
  api.py              → sérialise en JSON et répond au frontend
```

---

## Format des saves : GVAS (Unreal Engine 4.27)

Les fichiers `.sav` sont au format **GVAS**, un dictionnaire imbriqué encodé en binaire (pas du JSON). Le parseur `parse_save.py` est fait maison, résultat d'analyse binaire — ne pas modifier sans comprendre le format.

Types supportés : `IntProperty`, `FloatProperty`, `BoolProperty`, `StrProperty`, `EnumProperty`, `StructProperty`, `ArrayProperty`.

⚠️ `MapProperty` et `SetProperty` sont actuellement skippés.

---

## Déploiement

Cible : **Railway** (ou Vercel serverless).

Le frontend (Next.js sur Vercel) appelle ce backend via l'URL de production. En développement local, le frontend pointe sur `http://localhost:5000` via la variable `NEXT_PUBLIC_API_URL`.

---

## Commandes utiles

```bash
# Lancer l'API en local
python api.py

# Tester le parseur directement sur un fichier .sav
python parse_save.py Saved/SaveGames/<id>_Player.sav
```

---

## Notes

- Ne pas modifier les fichiers dans `Saved/` — ce sont de vraies saves de jeu
- Le mapping des GUIDs vient du projet open-source [AnthonyMichaelTDM/drg-completionist](https://github.com/AnthonyMichaelTDM/drg-completionist)
- Limite de taille fichier : **5 MB**
