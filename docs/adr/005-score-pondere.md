# ADR 005 — Score pondéré, poids recopiés dans chaque résultat

## Contexte

Un score global rend un tableau de bord lisible d'un coup d'œil. Il est aussi dangereux : il cache la façon dont il est calculé et invite à le prendre pour un verdict.

## Décision

Score = moyenne pondérée des contributions (1 / 0,5 / 0), contrôles non applicables exclus du calcul, poids et seuils documentés et surchargeables. Les poids employés sont **recopiés dans chaque résultat** au moment du run. Le score n'est jamais affiché sans le détail des contrôles.

## Conséquences

Une exécution consultée dans six mois reste explicable même si la configuration a changé entre-temps — c'est une dénormalisation assumée, et elle est là pour ça.

Corollaire : lorsqu'aucun contrôle n'a pu s'exécuter, le score vaut `null` et non 0. Un fichier vide n'a pas une qualité nulle, il n'a pas de qualité mesurée, et la nuance se perd entièrement si on affiche zéro.
