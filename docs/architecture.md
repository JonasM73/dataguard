# Architecture

## Vue d'ensemble

```
Source publique (URL https) ou fichier envoyé
        │
        ▼
┌─────────────────┐  schéma d'URL vérifié avant tout appel réseau,
│ 1. Ingestion    │  taille contrôlée pendant le téléchargement,
│                 │  checksum SHA-256, fichier brut conservé
└────────┬────────┘
         ▼
┌─────────────────┐  lecture en texte (aucune inférence de type),
│ 2. Profilage    │  schéma observé, volume
└────────┬────────┘
         ▼
┌─────────────────┐  huit contrôles indépendants,
│ 3. Contrôles    │  score pondéré, statut global
└────────┬────────┘
         ▼
┌─────────────────┐  diff volume / schéma / score / statuts
│ 4. Comparaison  │  avec l'exécution précédente
└────────┬────────┘
         ▼
┌─────────────────┐  runs, résultats, schémas, comparaisons
│ 5. Persistance  │  PostgreSQL
└────────┬────────┘
         ▼
┌─────────────────┐         ┌──────────────────────┐
│ 6. API FastAPI  │ ──────► │ 7. Dashboard React   │
│    contrat      │ OpenAPI │    types engendrés   │
└─────────────────┘         └──────────────────────┘
```

Les étapes 1 à 5 forment le pipeline (`app/pipeline.py`), appelé indifféremment par l'API ou par la CLI. Les deux chemins produisent le même run : il n'y a pas deux implémentations à maintenir et à tester.

## Découpage et dépendances

| Module | Rôle | Ce qu'il ignore |
|---|---|---|
| `app/ingestion` | récupérer et lire un fichier | les contrôles, la base |
| `app/profiling` | relever et comparer des schémas | la base, l'API |
| `app/quality` | exécuter les contrôles, calculer le score | la base, l'API, le réseau |
| `app/comparison` | comparer deux exécutions | la base, l'API |
| `app/db` | modèles et session | les contrôles |
| `app/api` | contrat HTTP | la mécanique des contrôles |
| `app/pipeline.py` | orchestrer, persister | — |

La contrainte utile est celle du moteur de contrôles : il ne connaît ni base ni API. C'est ce qui permet de le tester sans rien démarrer, et d'ajouter un contrôle sans toucher au reste de la chaîne. Les 67 tests unitaires en découlent directement — ils tournent sur des DataFrames, sans réseau ni base.

## Configuration d'un dataset

Les règles ne sont pas codées en dur. Chaque dataset porte une configuration JSON qui déclare, par colonne, le type attendu, les bornes, les valeurs autorisées, le motif et les seuils de valeurs absentes ; et pour le dataset, la clé d'unicité, les colonnes de fraîcheur, la tolérance de volume, les poids et les règles de cohérence.

Conséquence : suivre un second dataset ne demande pas une ligne de code, seulement une configuration et un schéma de référence.

La fréquence attendue fait exception. Elle vit dans la colonne `expected_frequency` du dataset, et le pipeline l'injecte dans la configuration avant d'exécuter les contrôles. La stocker aux deux endroits l'aurait fait diverger tôt ou tard.

## Base de données

Six tables : `sources`, `datasets`, `ingestion_runs`, `quality_results`, `schema_fields`, `run_comparisons`.

Deux choix méritent d'être signalés.

Les statuts sont stockés en texte et non en type énuméré PostgreSQL : ajouter une valeur ne demande alors aucune migration délicate, et la validation reste assurée côté Python.

Les poids sont recopiés dans `quality_results` au moment du run. C'est une dénormalisation assumée : sans elle, changer la configuration d'un dataset rendrait inexplicables tous ses runs passés, puisque leur score aurait été calculé avec des poids qui n'existent plus.

`run_comparisons.run_id` porte une contrainte d'unicité : une exécution n'est comparée qu'une fois.

## Traitement synchrone

`POST /runs` exécute le pipeline et répond une fois terminé. Sur un fichier de quelques mégaoctets le traitement prend une fraction de seconde, ce qui ne justifie pas d'introduire une file de tâches, un worker et un état « en cours » à afficher. Si la limite de taille augmentait, le passage en tâche de fond serait la première évolution à faire.

## Erreurs

Un échec technique — source injoignable, fichier vide, encodage illisible, dépassement de taille — n'interrompt pas le traitement par une exception qui remonterait à l'appelant. Il produit un run enregistré en `failed`, avec un code, un message exploitable et aucun score. L'historique conserve donc la trace des tentatives ratées, ce qui est précisément ce qu'on veut observer quand une source se met à tomber régulièrement.

Côté API, toutes les erreurs sortent sous la même forme :

```json
{ "error": { "code": "run_not_found", "message": "…", "details": null } }
```

Le dashboard n'a ainsi qu'un seul cas d'erreur à traiter, quelle que soit l'origine du problème. Les erreurs inattendues portent en plus l'identifiant de trace, pour relier ce que voit l'utilisateur à ce que montrent les traces côté serveur.

## Observabilité

Branchée dès les fondations, et non ajoutée après coup — une instrumentation rétro-adaptée est toujours bâclée.

- Logs structurés JSON, chaque étape portant le `run_id` : un incident se reconstitue en filtrant sur un seul identifiant.
- Un span racine par exécution, dont les quatre étapes du pipeline sont les
  enfants : elles partagent son identifiant de trace, et l'enchaînement se lit
  d'un bloc. Des spans frères sans racine commune donneraient quatre traces
  isolées, ce qui reviendrait à ne rien observer du tout.
- Un span par requête HTTP également. Export console par défaut, donc aucun
  service tiers requis en local ; `DATAGUARD_OTEL_EXPORTER=otlp` bascule vers un
  collecteur si l'on en démarre un.
- La CLI n'affiche pas les traces : l'export console déverse un objet JSON par
  span sur la sortie standard et noierait le résultat de la commande. Elles se
  demandent avec `--trace`. Dans l'API elles partent dans le journal du serveur,
  où elles sont à leur place.
- Durée, volume, statut et score de chaque run stockés en base et visibles dans le dashboard.

## Frontend

React, TypeScript, Vite, TanStack Query pour le cache et les états de chargement, Recharts pour la courbe de score.

Les types du contrat sont engendrés depuis `openapi.json` et vérifiés en CI. Un champ renommé côté API casse la compilation du dashboard, au lieu de produire un `undefined` silencieux à l'écran.

Trois règles d'affichage tiennent au sujet : un statut est toujours écrit et pas seulement coloré ; le score n'apparaît jamais sans le détail qui le compose ; un score absent s'affiche comme absent et non comme un zéro.

## Sécurité

- `.env` n'est jamais versionné, `.env.example` documente les clés.
- Seules les URL `https` sont acceptées, et la taille est contrôlée pendant le téléchargement — la vérifier après coup ne protégerait de rien.
- Lecture en texte avec encodage explicite.
- Requêtes paramétrées via SQLAlchemy uniquement.
- CORS restreint à l'origine du dashboard.
- Conteneur applicatif exécuté sous un utilisateur non privilégié.
- Audit des dépendances en CI (`pip-audit`, `npm audit`).
- Aucune donnée personnelle : la source ne décrit que des points de vente.
