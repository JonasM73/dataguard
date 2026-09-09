# ADR 009 — Licence MIT, dépôt public, aucune donnée réelle versionnée

## Contexte

Le dépôt est destiné à être lu par d'autres, et la source réelle pèse près de 20 Mo.

## Décision

Licence MIT, dépôt public dès le départ. Aucun fichier CSV n'est versionné : ni les exports de la source réelle, ni les fichiers synthétiques. Sont suivis le générateur `scripts/generate_samples.py`, le schéma de référence relevé sur la source, et la configuration du dataset — de quoi tout reconstruire à l'identique.

## Conséquences

Le dépôt reste léger et sa licence est claire. Les tests ne dépendent d'aucun téléchargement, donc d'aucune connexion réseau ni d'aucune disponibilité de service tiers — ce qui est cohérent avec l'objet même du projet : une source publique peut disparaître ou changer, c'est précisément ce que DataGuard doit détecter.

Les fichiers synthétiques sont exclus pour deux raisons qui se renforcent : ils pèsent 13 Mo, et ils portent des dates absolues qui vieillissent. Les versionner alourdirait le dépôt tout en y figeant des fichiers qui deviendraient trompeurs au bout de quelques jours. `make samples` les régénère à l'identique, et les tests régénèrent les leurs à chaque exécution.
