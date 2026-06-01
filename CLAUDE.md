# DRG Dashboard — CLAUDE.md

## Contexte du projet

Dashboard web pour afficher les statistiques de joueurs Deep Rock Galactic, parsées depuis les fichiers de sauvegarde du jeu.

**Développeur :** Mat — développeur fullstack débutant. Ce projet est un exercice d'apprentissage.

**Approche pédagogique :**
- Préférer les analogies pour expliquer les concepts
- Découper les notions complexes en petits morceaux
- Expliquer le "pourquoi" avant le "comment"
- Claude Code guide pas à pas : ne pas écrire de grosses quantités de code d'un coup, expliquer chaque étape avant de la coder
- Code lisible avant tout : noms de variables compréhensibles en anglais, commentaires utiles
- Ne pas hésiter à montrer des exemples concrets avant d'abstraire

---

## Architecture du projet

Le projet est séparé en deux dépôts / deux déploiements distincts.

```
drg_dashboard/          ← ce dépôt (backend Python)
drg_dashboard_frontend/ ← dépôt séparé (frontend Next.js)
```

### Pourquoi séparer backend et frontend ?

Le backend est en Python (Flask). Next.js est en JavaScript/TypeScript. Ces deux langages ne peuvent pas tourner dans le même processus — ils doivent donc être déployés séparément. Le frontend appelle le backend via HTTP, comme deux applications qui se parlent par téléphone.

---

## Stack technique

### Backend — Python Flask
- **Langage :** Python 3.11+
- **Framework :** Flask + flask-cors
- **Rôle :** Parser les fichiers `.sav`, construire le JSON de stats, exposer `/api/parse`
- **Déploiement :** Vercel (fonction serverless) ou Railway
- **Fichiers clés :**
  - `parse_save.py` — parseur GVAS (format binaire Unreal Engine 4.27)
  - `guid_mapper.py` — traduction GUIDs → noms lisibles
  - `stats_builder.py` — assemblage des données pour le frontend
  - `api.py` — endpoint Flask `POST /api/parse`
  - `guids.json` — mapping overclocks/cosmétiques (source : AnthonyMichaelTDM)
  - `stat_guids.json` — mapping stats de mission (extrait depuis les assets du jeu via FModel)

### Frontend — Next.js + TypeScript
- **Langage :** TypeScript (typage statique = moins de bugs, meilleure autocomplétion)
- **Framework :** Next.js 14 (App Router)
- **Styling :** Tailwind CSS (classes utilitaires, pas de CSS à écrire à la main)
- **Graphiques :** Recharts (bibliothèque de charts React, simple et bien documentée)
- **Déploiement :** Vercel
- **Thème :** Sombre obligatoirement (les icônes de perks sont blanches sur fond transparent)

### Base de données — PostgreSQL via Supabase
- **Pourquoi PostgreSQL ?** Base de données relationnelle, standard de l'industrie, parfaite pour des données structurées comme des stats de joueurs
- **Pourquoi Supabase ?** PostgreSQL hébergé + interface web claire + SDK JavaScript simple + tier gratuit généreux
- **Rôle :** Stocker les stats des joueurs après upload pour alimenter un leaderboard public
- **Accès :** Depuis le frontend Next.js via le SDK `@supabase/supabase-js`

---

## Flux de données

```
1. Joueur uploade son .sav + entre son pseudo sur /
2. Next.js envoie le fichier au backend Flask (POST /api/parse)
3. Flask parse le .sav, retourne un JSON de stats
4. Next.js stocke ces stats dans Supabase (table players)
5. Next.js affiche le dashboard sur /dashboard
6. /leaderboard lit Supabase et affiche le classement
```

---

## Schéma de la base de données (cible)

```sql
CREATE TABLE players (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name              text NOT NULL,
  uploaded_at       timestamptz DEFAULT now(),

  -- Stats globales
  total_missions    integer,
  total_kills       integer,
  total_time_s      integer,    -- temps en mission (secondes)
  total_distance_cm bigint,     -- distance parcourue (centimètres)
  total_downs       integer,
  perk_points       integer,
  overclocks_forged integer,

  -- Missions par classe
  missions_driller  integer,
  missions_gunner   integer,
  missions_engineer integer,
  missions_scout    integer,

  -- Kills par classe
  kills_driller     integer,
  kills_gunner      integer,
  kills_engineer    integer,
  kills_scout       integer
);
```

---

## Pages du frontend (structure cible)

```
/             → Page d'accueil : upload du .sav + champ pseudo
/dashboard    → Dashboard du joueur (stats après upload)
/leaderboard  → Classement public des joueurs (données depuis Supabase)
```

---

## Structure du projet frontend (cible)

```
drg_dashboard_frontend/
├── app/
│   ├── page.tsx                ← page d'accueil (upload)
│   ├── dashboard/
│   │   └── page.tsx            ← dashboard du joueur
│   └── leaderboard/
│       └── page.tsx            ← classement public
├── components/
│   ├── UploadForm.tsx          ← formulaire upload + pseudo
│   ├── PlayerHeader.tsx        ← nom du joueur + stats globales
│   ├── ClassTabs.tsx           ← onglets Driller / Gunner / Engineer / Scout
│   ├── StatCard.tsx            ← carte d'une stat individuelle
│   ├── KillsChart.tsx          ← graphique kills par classe
│   └── MissionsChart.tsx       ← graphique missions par type
├── lib/
│   ├── api.ts                  ← appels au backend Flask
│   ├── supabase.ts             ← client Supabase
│   └── types.ts                ← types TypeScript partagés
└── public/
    └── icons/                  ← copie des assets (classes, perks...)
```

---

## Règles de code

- **Noms de variables :** anglais, descriptifs (`playerStats` pas `ps`, `missionCount` pas `n`)
- **Commentaires :** en français si ça aide Mat à comprendre, sinon en anglais
- **Composants React :** un composant = un fichier, nommé en PascalCase (`PlayerHeader.tsx`)
- **Types TypeScript :** toujours typer les props et les retours de fonction
- **Pas de code magique :** si quelque chose n'est pas évident, ajouter un commentaire
- **Petits pas :** expliquer avant de coder, une fonctionnalité à la fois

---

## Format des saves : GVAS (Unreal Engine 4.27)

Les fichiers `.sav` sont au format **GVAS** (Unreal Engine). C'est un dictionnaire imbriqué encodé en binaire plutôt qu'en texte JSON.

### Règles de parsing (découvertes par analyse binaire)

Chaque propriété a la structure : `[nom_str][type_str][size i64][payload]`

| Type | Règle de taille | Lecture |
|------|----------------|---------|
| `IntProperty` | `size` = données seules (tag exclu) | `tag(1) + i32(4)` |
| `FloatProperty` | idem | `tag(1) + f32(4)` |
| `BoolProperty` | `size=0`, tag = la valeur | `u8(1) + padding(1)` |
| `StrProperty` | idem scalaire | `tag(1) + string` |
| `EnumProperty` | `size` = payload complet | `enum_type_str + tag(1) + value_str` |
| `StructProperty` | `size` = données des sous-props seulement (après struct_type + 17 bytes GUID) | `struct_type_str + GUID(16) + tag(1) + sub_props + None` |
| `ArrayProperty` | `size` = payload − len(itype_str) − 1(tag) → `true_end = payload_start + len(itype_bytes) + 1 + size` | Voir parseur |
| `MapProperty` / `SetProperty` | ⚠️ Non encore parsés (skippés) | — |
| Types inconnus | Traités comme scalaires : `tag(1) + size` bytes | — |

### Données disponibles dans le JSON

- **`MissionStatsSave`** — compteurs de stats mappés via `stat_guids.json`
- **`OwnedPerks`** — perks débloqués
- **`SchematicSave`** — overclocks forgés / non forgés
- **`SeasonSave`** — progression des saisons
- **`WeaponMaintenance`** — niveau des armes
- **`PerkPoints`** — points de perks disponibles
- **`JettyBootsSave`** — scores du mini-jeu Jetty Boots

⚠️ **Données skippées :** `MapProperty` et `SetProperty` non encore parsés.

---

## Commandes utiles

```bash
# Backend Python
python api.py                    # lancer l'API en local (port 5000)
python3 parse_save.py Saved/SaveGames/76561197983653885_Player.sav

# Frontend Next.js (depuis drg_dashboard_frontend/)
npm run dev                      # lancer en développement (port 3000)
npm run build                    # build de production
```

---

## Ce que Claude Code doit savoir

- Ne pas modifier les fichiers dans `Saved/` — ce sont les vraies saves du jeu
- Le parseur `parse_save.py` est fait maison, résultat de reverse engineering — ne pas le réécrire
- Les GUIDs sont mappés via `guid_mapper.py` qui lit `guids.json` et `stat_guids.json`
- Le thème est **sombre** — les icônes de perks sont blanches sur fond transparent
- L'objectif est un dashboard **lisible et pédagogique**, pas un éditeur de saves
- Mat est débutant : toujours expliquer avant de coder, proposer une étape à la fois

---

## État actuel (mai 2026)

### Ce qui est terminé ✅

**Backend**
- Parseur GVAS complet (`parse_save.py`) — tous les types sauf `MapProperty` et `SetProperty`
- Mapping GUIDs → noms lisibles (`guid_mapper.py`, `guids.json`, `stat_guids.json`)
- `stats_builder.py` — construit le JSON final envoyé au frontend :
  - `_format_stat_name()` : convertit les noms d'assets en texte lisible (`MS_Completed_DeepScan` → `Deep Scan`)
  - `UNIT_MAP` : unités pour distance (cm) et temps (s)
  - Filtrage des stats avec GUID inconnu
- API Flask (`api.py`) — endpoint `POST /api/parse` fonctionnel en local

**Frontend (dépôt séparé `drg_dashboard_frontend`)**
- Upload `.sav` + pseudo → appel backend → stockage Supabase
- Page `/dashboard` : hero stats, cards par classe, overclocks avec icônes d'armes, mission stats avec onglets par catégorie
- Page `/leaderboard` : classement triable depuis Supabase
- Navbar active, police Barlow Condensed, thème DRG brun chaud

### Ce qui reste à faire 🔜

**Design (priorité actuelle)**
- Refonte DA fidèle à DRG : coins biseautés (`clip-path`) sur les cards, séparateurs oranges
- Cohérence des majuscules sur tous les labels
- Ajouter icônes minerais dans Mission Stats → section Mining
- Ajouter icônes missions/assignments dans les onglets Mission Stats

**Dashboard — fonctionnalités**
- Réordonner : Mission Stats avant Overclocks
- Camembert par stat de classe (clic sur une stat → camembert coloré par classe)
- Filtre par classe dans la section Overclocks
- Nombre d'overclocks par classe affiché dans le header de section

**Déploiement**
- Backend sur Railway (ou Vercel serverless)
- Frontend sur Vercel
- Diagramme d'architecture dans le README GitHub
