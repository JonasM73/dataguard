# ADR 006 — Fraîcheur : le contenu d'abord, le transport ensuite

## Contexte

La date de modification d'un fichier ne dit rien sur la fraîcheur des données qu'il contient. Un export régénéré chaque nuit paraît toujours frais, même si les données datent de la semaine dernière.

## Décision

Ordre de priorité strict : colonne de date déclarée dans la configuration, puis en-tête HTTP `Last-Modified`, puis date de modification du fichier, sinon contrôle non applicable. L'origine retenue est stockée et affichée à l'utilisateur.

## Conséquences

Le contrôle garde un sens sur un fichier régénéré quotidiennement. Un dataset doit déclarer sa colonne de date pour bénéficier du meilleur niveau de fiabilité.

Afficher l'origine n'est pas cosmétique : « dernière donnée le 8 septembre (colonne `Prix Gazole mis à jour le`) » et « fichier modifié le 8 septembre » n'ont pas la même valeur, et l'utilisateur doit pouvoir faire la différence.
