# ADR 004 — Pipeline synchrone

## Contexte

`POST /runs` déclenche un traitement complet : téléchargement, lecture, contrôles, comparaison, écriture.

## Décision

Le traitement est synchrone : l'API répond une fois le run terminé. Pas de file de tâches, pas de worker, pas d'état « en cours ».

## Conséquences

Aucun composant supplémentaire à déployer ni à surveiller. Mesuré sur un fichier de 1 000 lignes et 47 colonnes, un run complet prend de 112 à 136 ms — largement en deçà de ce qui justifierait de l'asynchrone.

La limite est assumée : la requête HTTP reste ouverte pendant le traitement. Si la limite de taille des fichiers augmentait, le passage en tâche de fond serait la première évolution à faire.
