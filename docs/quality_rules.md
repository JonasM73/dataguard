# Règles de qualité

Ce document décrit exactement ce que chaque contrôle mesure, avec quels seuils, et comment le score en découle. Il doit rester synchronisé avec `backend/app/quality/checks.py` : si les deux divergent, c'est le code qui fait foi et le document qui est en retard.

## Principe commun

Chaque contrôle évalue les colonnes concernées **une par une**, puis agrège les statuts au plus grave. Un pourcentage calculé sur l'ensemble du fichier diluerait une colonne entièrement cassée dans la masse des colonnes saines : 1 000 valeurs illisibles sur 20 000 cellules font 5 % du fichier, mais 100 % de la colonne. C'est le second chiffre qui compte.

## Quatre statuts

| Statut | Sens | Contribution au score |
|---|---|---|
| `success` | le contrôle passe | 1 |
| `warning` | anomalie tolérable | 0,5 |
| `failed` | anomalie disqualifiante | 0 |
| `skipped` | contrôle non applicable | exclu du calcul |

`skipped` n'est pas un échec déguisé. Le contrôle de volume sans exécution précédente, ou le contrôle de schéma sans schéma de référence, n'ont rien à mesurer : les compter comme des échecs punirait le premier run de chaque dataset.

Un seuil d'alerte est franchi **dès qu'on le dépasse strictement**. Un seuil à 0 signifie donc « la moindre occurrence déclenche une alerte ».

## Quelles colonnes sont contrôlées

Une colonne n'est soumise qu'aux contrôles dont elle déclare les règles dans la configuration du dataset :

| Contrôle | S'applique si la colonne déclare |
|---|---|
| Complétude | `required`, `null_warn_pct` ou `null_fail_pct` |
| Types | `type` autre que `string` |
| Plages | `min`, `max`, `allowed_values` ou `pattern` |
| Schéma | rien : il porte sur les 47 colonnes du fichier de référence |

Une colonne absente de la configuration n'est donc suivie que par le contrôle de schéma. C'est voulu : les colonnes JSON imbriquées de la source (`horaires`, `services`, `prix`, `rupture`) n'ont pas de règle de forme utile, mais leur disparition doit être signalée.

## Couverture : ce qu'un contrôle a réellement regardé

Un contrôle ne peut évaluer que les colonnes présentes dans le fichier. Si la
configuration lui en désigne dix-sept et que sept seulement s'y trouvent, il
rend son verdict sur ces sept-là — et c'est un piège, parce qu'un « conforme »
ne dit alors rien des dix autres.

La complétude, les types et les plages publient donc dans leur détail
`configured_columns`, `checked_columns` et `missing_columns`, et le dashboard
affiche la proportion dès qu'elle est incomplète.

Le statut, lui, n'est pas dégradé pour autant : la disparition d'une colonne
attendue est déjà signalée, une fois, par le contrôle de schéma. La faire
ressortir une seconde fois dans trois autres contrôles compterait le même
incident quatre fois et ferait chuter le score bien au-delà de ce qu'il vaut.
Un contrôle dit donc ce qu'il a vu et ce qu'il n'a pas pu voir ; c'est le
contrôle de schéma qui juge la disparition.

## Les huit contrôles

### Schéma — poids 3

Compare le schéma observé au schéma de référence : le schéma déclaré sur le dataset, à défaut celui de la première exécution réussie.

| Différence | Statut |
|---|---|
| colonne ajoutée | `warning` |
| colonne supprimée | `failed` |
| colonne renommée | `failed` |
| type d'une colonne changé | `failed` |

Une colonne disparue et une colonne apparue **à la même position** sont traitées comme un renommage. Les signaler comme une suppression doublée d'un ajout ferait croire à une perte de donnée là où il n'y a qu'un changement de nom. La limite est assumée : deux colonnes échangées à la même position seraient mal interprétées.

Le type observé n'est pas le dtype brut de Pandas — un CSV lu en texte donnerait `object` partout, ce qui ne dirait rien. Chaque colonne est confrontée au type que la configuration déclare, et ce type n'est retenu que si au moins 90 % des valeurs non nulles s'y convertissent. Une colonne de nombres passée à la virgule décimale bascule ainsi en `string`, et le changement est signalé.

### Types — poids 3

Compte les valeurs non nulles que le type déclaré rejette, colonne par colonne.

| Part de valeurs non convertibles | Statut |
|---|---|
| 0 % | `success` |
| jusqu'à 1 % | `warning` |
| au-delà de 1 % | `failed` |

Réglable par `defaults.type_warn_pct` et `defaults.type_fail_pct`.

### Unicité — poids 3

Compte les lignes en double sur `key_columns`.

| Part de doublons | Statut |
|---|---|
| 0 % | `success` |
| jusqu'à 0,1 % | `warning` |
| au-delà de 0,1 % | `failed` |

Non applicable si aucune clé n'est déclarée ou si les colonnes clés sont absentes.

### Complétude — poids 2

Taux de valeurs absentes par colonne.

- colonne `required` : la moindre absence donne `failed` ;
- sinon, seuils `null_warn_pct` et `null_fail_pct` de la colonne, à défaut ceux de `defaults`.

Les seuils sont propres à chaque colonne, et c'est essentiel sur cette source : le SP95 est absent de 70 % des stations et le GPLc de 85 %, non par défaut de qualité mais parce que ces carburants n'y sont pas distribués. Un seuil unique à 5 % ferait échouer le contrôle sur un fichier parfaitement sain.

### Plages — poids 2

Selon ce que la colonne déclare : bornes `min`/`max`, liste `allowed_values`, ou motif `pattern`. Mêmes seuils que les types (0 % / 1 %).

Les valeurs non convertibles en nombre ne sont pas comptées ici : elles relèvent du contrôle de type, et les compter deux fois sanctionnerait doublement la même anomalie.

Les bornes expriment la **plausibilité**, pas les valeurs observées. Un prix de carburant est borné entre 0,50 € et 5 € afin d'attraper un 0,00 ou un 12,50 ; le resserrer autour du marché du jour transformerait chaque variation de prix en incident.

### Fraîcheur — poids 2

La date retenue suit un ordre de priorité strict :

1. le maximum des colonnes de date déclarées dans `freshness.columns` ;
2. l'en-tête HTTP `Last-Modified`, pour une source téléchargée ;
3. la date de modification du fichier, pour une source locale ;
4. sinon le contrôle est `skipped`.

L'origine retenue est stockée et affichée. La distinction n'est pas cosmétique : un fichier régénéré chaque nuit avec des données de la semaine dernière est frais au sens du fichier et périmé au sens utile. Seule la première source le révèle.

Avec `f` la fréquence attendue du dataset :

| Âge de la donnée | Statut |
|---|---|
| jusqu'à 1,5 × f | `success` |
| jusqu'à 3 × f | `warning` |
| au-delà | `failed` |

### Volume — poids 1

Variation du nombre de lignes par rapport à l'exécution précédente : `warning` au-delà de 10 %, `failed` au-delà de 50 %. Un fichier sans aucune ligne est `failed` — mais en pratique l'ingestion le rejette avant, et le run n'a alors pas de score du tout.

Non applicable sans exécution précédente.

### Cohérence — poids 1

Règles inter-colonnes déclarées dans `consistency.rules`. Une seule est implémentée : `not_in_future`, qui vérifie qu'aucune date de mise à jour n'est postérieure à l'ingestion, avec une tolérance de 15 minutes pour absorber les écarts d'horloge.

Cette règle n'est pas théorique : l'export réel du 9 septembre 2026 portait des dates de mise à jour environ une heure dans le futur.

Mêmes seuils que les types (0 % / 1 %).

## Score

```
score = Σ(poids × contribution) / Σ(poids) × 100
```

sur les seuls contrôles non `skipped`.

Exemple, sept contrôles exécutés dont la complétude en alerte et le volume en échec :

```
(3 + 3 + 3 + 2×0,5 + 2 + 2 + 0) / (3 + 3 + 3 + 2 + 2 + 2 + 1) = 14 / 16 = 87,5
```

Si aucun contrôle n'a pu s'exécuter, le score vaut `null` et non 0 : afficher zéro laisserait croire à une qualité nulle alors que rien n'a été mesuré.

## Statut global d'une exécution

1. `failed` si l'ingestion a échoué techniquement, ou si un contrôle de poids ≥ 3 est en échec ;
2. sinon `warning` si au moins un contrôle est en alerte ou en échec ;
3. sinon `success`.

Le seuil de criticité est réglable par `critical_weight`. La logique : un schéma cassé, une colonne inexploitable ou des doublons rendent le dataset inutilisable en aval, alors qu'une donnée un peu périmée ou un volume qui bouge méritent un signalement sans disqualifier le fichier.

## Poids par défaut

| Contrôle | Poids | Pourquoi |
|---|---|---|
| Schéma | 3 | un schéma changé casse tout ce qui est en aval |
| Types | 3 | une colonne inexploitable rend le dataset inutilisable |
| Unicité | 3 | des doublons faussent toute agrégation |
| Complétude | 2 | pénalisant, mais souvent partiellement acceptable |
| Plages | 2 | signale des valeurs suspectes, pas nécessairement fausses |
| Fraîcheur | 2 | une donnée périmée est fiable mais inutile |
| Volume | 1 | signal d'alerte, rarement bloquant à lui seul |
| Cohérence | 1 | dépend entièrement des règles déclarées |

Les poids sont surchargeables par dataset et **recopiés dans chaque résultat** au moment du run, afin qu'une exécution ancienne reste explicable après un changement de configuration.

## Ajouter un contrôle

1. Écrire une classe avec `name`, `dimension` et `run(ctx) -> CheckResult` dans `checks.py`.
2. L'ajouter à `ALL_CHECKS`.
3. Lui donner un poids par défaut dans la configuration du dataset.
4. Ajouter un fichier synthétique dans `scripts/generate_samples.py` qui déclenche ce contrôle et lui seul.
5. Ajouter la ligne correspondante à `MATRIX` dans `tests/unit/test_checks.py`.
6. Documenter la règle ici.

L'étape 4 compte autant que les autres : un contrôle sans fichier qui le déclenche n'est pas testé, et un fichier qui déclenche deux contrôles ne permet plus de savoir lequel a régressé.
