# ADR 001 — Un dataset, un format, huit contrôles

## Contexte

Le risque principal d'un projet personnel est de devenir une plateforme générique jamais terminée : chaque idée nouvelle repousse la première version utilisable.

## Décision

La première version traite un seul dataset réel, un seul format d'entrée (CSV) et au plus huit contrôles. JSON, GTFS, multi-sources et planification sont explicitement remis à plus tard.

## Conséquences

Le périmètre est fermé ; les idées nouvelles vont dans la section « Pistes » du README plutôt que dans le code. En contrepartie, la configuration reste pilotée par la donnée : suivre un second dataset ne demandera pas une ligne de code, seulement une configuration et un schéma de référence.
