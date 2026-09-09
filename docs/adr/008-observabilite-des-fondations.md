# ADR 008 — Observabilité branchée dès les fondations

## Contexte

L'instrumentation ajoutée en fin de projet est systématiquement bâclée : elle se greffe sur du code qui n'a pas été écrit pour elle.

## Décision

Logs structurés (structlog) et traces OpenTelemetry sont en place dès les premières fondations, avec export console. Chaque événement porte le `run_id`. Chaque exécution ouvre un span racine dont les étapes du pipeline sont les enfants, de sorte qu'elles partagent un même identifiant de trace.

## Conséquences

Aucun service supplémentaire n'est requis pour démarrer, et chaque étape ajoutée ensuite hérite du contexte de trace sans travail particulier. Un incident se reconstitue en filtrant les logs sur un seul identifiant.

La première exécution réelle a montré deux défauts que l'écriture seule n'avait pas révélés : les étapes ouvraient chacune une trace isolée, faute de span racine, et la CLI déversait un objet JSON par span sur sa sortie standard, noyant le résultat que la commande devait montrer. Le span racine corrige le premier ; les traces sont désormais muettes au terminal sauf `--trace`, l'API continuant de les émettre dans son journal.

Jaeger, les métriques et la corrélation entre trace API et trace pipeline restent à faire ; la bascule se fait par `DATAGUARD_OTEL_EXPORTER=otlp`.
