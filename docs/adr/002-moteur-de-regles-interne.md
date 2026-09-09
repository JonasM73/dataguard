# ADR 002 — Un moteur de règles interne plutôt que Great Expectations ou Soda

## Contexte

Des outils matures existent : Great Expectations, Soda Core, Pandera, dbt tests. Les utiliser ferait gagner des centaines de règles prêtes à l'emploi.

## Décision

Écrire un petit moteur en Python — une classe par contrôle, une interface commune — en reprenant le vocabulaire de ces outils (check, dimension, seuil, statut).

## Conséquences

Chaque règle tient en quelques lignes lisibles, se teste isolément et s'explique sans documentation externe. On renonce au catalogue de règles existantes et à leur robustesse éprouvée. Le vocabulaire commun laisse le passage à Pandera ou Great Expectations ouvert : les concepts se correspondent terme à terme.
