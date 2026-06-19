# PROGRESS.md — Journal de progression DRG Dashboard

## Statut global

| Étape | Statut |
|-------|--------|
| 1. Parser GVAS → JSON | ✅ Fonctionnel (partiel) |
| 2. Planification stack technique | ✅ Terminé |
| 3. Backend API | 🔜 À faire |
| 4. Frontend dashboard | 🔜 À faire |
| 5. Mapping GUID → noms lisibles | 🔜 À faire (guids.json dispo) |
| 6. Déploiement | ⬜ À faire |

---

## Étape 1 : Parser GVAS → JSON

### Résumé

Fichier : `parse_save.py`
Langue : Python 3, aucune dépendance externe.

Le parseur convertit les fichiers `.sav` (format binaire GVAS d'Unreal Engine 4.27) en dictionnaire Python / JSON.

**Résultat actuel :** 20 propriétés de premier niveau parsées, couvrant l'essentiel des stats utiles pour le dashboard.

### Ce qui fonctionne

- `IntProperty`, `FloatProperty`, `BoolProperty`, `StrProperty`, `NameProperty`
- `EnumProperty`, `ObjectProperty`
- `StructProperty` (y compris imbriqués récursivement)
- `ArrayProperty` de tous les types ci-dessus + `ArrayProperty` de `StructProperty`
- Lecture correcte du header GVAS (magic, version, build string, custom format, save class)

### Ce qui est skippé (à implémenter si besoin)

- `MapProperty` — présent dans `UnLockedMissionParameters` et quelques autres
- `SetProperty` — rare dans ce save
- `MulticastInlineDelegateProperty` — callbacks internes du jeu, inutiles pour le dashboard

### Bugs résolus (leçons apprises)

#### Bug 1 : Calcul de `data_end` pour `StructProperty`

**Problème :** On calculait `data_end = payload_start + size` mais le parseur s'arrêtait trop tôt.

**Cause :** Pour `StructProperty`, `size` = taille des **données brutes** (sous-props + None terminal) **seulement**, après `struct_type_str` (variable) et 17 bytes de GUID+tag. Ces 17+ bytes ne sont **pas** comptés dans `size`.

**Fix :** `data_end = o_after_struct_type + 17 + size` (on lit struct_type et le GUID d'abord, puis on calcule data_end).

#### Bug 2 : Calcul de `true_end` pour `ArrayProperty` de `StructProperty`

**Problème :** Après le dernier item du struct array, l'offset réel dépassait notre `data_end` calculé de 20 bytes, causant un arrêt prématuré du parsing parent.

**Cause :** Pour `ArrayProperty`, `size` = payload total **moins** `len(itype_str_bytes) + 1(tag)`. Autrement dit, les bytes du type d'item et du tag ne sont pas inclus dans `size`.

**Fix :** `true_end = payload_start + len(itype_str_bytes) + 1 + size`

#### Bug 3 : Tag byte résiduel après types inconnus

**Problème :** Après avoir skippé `MulticastInlineDelegateProperty` avec `skip = o + size`, le parseur tombait sur un byte null inattendu et s'arrêtait.

**Cause :** Les types "scalaires" (y compris les types inconnus) ont un **tag byte** qui précède les données et qui n'est **pas** compté dans `size`. Notre skip ne consommait pas ce tag.

**Fix :** Pour les types inconnus, `skip = o + 1 + size` (le +1 pour le tag).

### Structure du JSON produit

```json
{
  "VersionNumber": 2,
  "PerkPoints": 87,
  "MissionStatsSave": {
    "Counters": [
      {
        "PlayerClassID": "ae56e180...",
        "MissionStatID": "f803c36f...",
        "Value": 13260048.0,
        "_type": "MissionStatCounter"
      }
    ]
  },
  "SchematicSave": {
    "ForgedSchematics": ["guid1", "guid2", ...],
    "OwnedSchematics": ["guid1", ...]
  },
  "SeasonSave": { "Seasons": [...] },
  "JettyBootsSave": {
    "HighScores": [
      { "PlayerName": "Bosco", "Score": 33 },
      ...
    ]
  }
}
```

---

## Étape 2 : Planification

### Stack technique retenue

```
Navigateur (React + TypeScript)
        ↕  HTTP (JSON)
Backend Python Flask  →  parse_save.py  →  guid_mapper.py  →  stats_builder.py
        ↕  déployé sur Vercel (fonction serverless)
Frontend React  →  déployé sur Vercel (CDN statique)
```

- **Backend :** Python Flask — un seul endpoint `POST /api/parse` (reçoit le `.sav`, renvoie du JSON, pas de stockage)
- **Frontend :** React + TypeScript — thème sombre (obligatoire : les icônes de perks sont blanches)
- **Déploiement :** Deux projets Vercel séparés (frontend + backend)
- **Mapping GUID :** `guids.json` depuis AnthonyMichaelTDM/DRG-Save-Editor (Season 6, 87.5KB)
- **Pas de stockage serveur** — le `.sav` est traité en mémoire uniquement (confidentialité)

### Décisions prises

1. Le joueur entre son pseudo au moment de l'upload (le fichier save ne contient pas le nom Steam directement)
2. Structure de la page : header (nom + niveau) → stats globales → onglets par classe
3. Thème sombre + couleurs par classe : Driller=#e6c020, Gunner=#d44a4a, Engineer=#5cba5c, Scout=#4a8fd4

### À faire à la fin du projet

> 📌 **Ajouter le diagramme d'architecture** (SVG de la stack technique) dans le dépôt GitHub et le référencer dans le `README.md` du projet.

---

## Notes techniques diverses

- Les Steam IDs dans le dossier `SaveGames/` identifient les joueurs : `76561197983653885` et `76561198000948560`
- Le jeu s'appelle "FSD" en interne (Fortnite... non : "For the Survivors Deep" — c'est le nom interne de DRG)
- La save class est `/Script/FSD.FSDSaveGame`
- Unreal Engine version : 4.27.2
- Les 290 compteurs dans `MissionStatsSave.Counters` sont identifiés par des paires de GUIDs : `(PlayerClassID, MissionStatID)`. Il faut une table externe pour savoir à quoi correspond chaque paire.

---

## Bugs résolus en session (juin 2026)

### Bug CLASS_GUID : rotation 3 classes (Driller ↔ Scout ↔ Gunner)

**Problème :** Les stats par classe (kills, temps, distance, downs) étaient attribuées à la mauvaise classe pour Driller, Gunner et Scout.

**Cause :** Le mapping `CLASS_GUIDS` dans `guid_mapper.py` était faux pour 3 des 4 classes (Engineer seul était correct). Les GUIDs formaient une rotation cyclique : ce qui était labellisé "Driller" correspondait en réalité à Scout, "Gunner" → Driller, "Scout" → Gunner.

**Preuve :** Temps Scout in-game = 2j18h38m20s = 239 900s. Le parser retournait 239 900s pour "Driller" → le GUID `30d8ea17...` = Scout.

**Fix :** `guid_mapper.py` corrigé + golden values des tests mis à jour.

**Migration Supabase :** SQL UPDATE atomique pour faire pivoter les 4 familles de colonnes (kills, time_s, distance_cm, downs) sur tous les joueurs existants, sans passer par des colonnes temporaires (PostgreSQL évalue tout le RHS avant d'écrire).

---

## Tâches à faire

### Architecture — Dashboard fetch depuis Supabase

**Contexte :** Actuellement, `/dashboard` affiche les stats depuis la réponse de l'API Flask (état client React). Le leaderboard, lui, lit Supabase directement.
Conséquence : après la migration SQL (correction CLASS_GUID), le leaderboard était à jour mais le dashboard affichait encore les anciennes valeurs (cache client). Il fallait vider le cache ou re-uploader.

**Tâche :** Faire en sorte que `/dashboard` récupère ses données depuis Supabase (colonne `raw_data`) via le `pin_hash` du joueur, plutôt que de stocker la réponse de l'API dans l'état React.

**Prérequis :**
- Vérifier que `raw_data` contient bien le JSON complet du dashboard (`SELECT raw_data FROM players LIMIT 1;`)
- Le `pin_hash` doit être transmis au frontend après l'upload (déjà dans la réponse ?)

**Avantage :** Une seule source de vérité (Supabase). Toute migration/correction côté DB se reflète immédiatement dans le dashboard sans re-upload.

---

### TODO sync Notion (page DRGlytics — 2026-06-15)

#### Fonctionnalités / UX
- [ ] Feedback visuel en cas de soucis lors de l'upload (ajouter au formulaire)
- [ ] Changer l'icône d'onglet du site + le nom de la page affiché dans l'onglet
- [ ] "Best class" — définir sur quelle stat elle est calculée
- [ ] Bounty targets — définir sur quelle base le maximum est calculé
- [ ] Page Options non traduite (i18n incomplète)
- [ ] Régler le débordement dans le memorial sur "COMPANY QUOTA FULFILLMENT"
- [ ] Corriger le changement de pseudo dans les options

#### Documentation / Architecture
- [ ] Schéma BDD (ajouter dans le README et dans le projet)
- [ ] Schéma archi (diagramme flux front/back à illustrer)
- [ ] Expliquer le flux de données front/back (README ou /doc)
- [ ] Mettre les schémas dans le README
- [ ] Faire une doc HTML intégrée au projet (`*.vercel.app/doc`)

#### Déploiement / Infra
- [ ] Voir déploiement (backend Render free → cold start 30-60s, penser à upgrader)
- [ ] Beta test pour retours utilisateurs

#### Sécurité
- [ ] Validation stricte du fichier `.sav` côté backend
- [ ] Timeout du parser (éviter les sav malformés qui bloqueraient le serveur)
- [ ] Ajouter l'authentification avec Supabase Auth (sinon BetterAuth)

#### Exploration / Recherche
- [ ] Voir faisabilité de récupérer les succès Steam grâce au SteamID dans la save
- [ ] Checker les stats de Tom (vérification cross-joueur après correction CLASS_GUID)

#### Audits restants (Notion)
- [ ] 04 — Audit Gestion d'État & Data Flow
- [ ] 05 — Audit UI / UX / Responsive
- [ ] 06 — Audit Accessibilité (a11y)
- [ ] 07 — Audit Backend / API
- [ ] 08 — Audit Base de Données
- [ ] 09 — Audit Performance
- [ ] 10 — Audit Tests & Fiabilité
- [ ] 11 — Audit DevOps / Infra
