# ADR 007 — Types du dashboard engendrés depuis le contrat OpenAPI

## Contexte

Maintenir à la main des types TypeScript qui doublent les schémas Pydantic garantit qu'ils divergeront. La divergence se manifeste au pire endroit : un `undefined` silencieux à l'écran, en production.

## Décision

`frontend/src/api/schema.d.ts` est produit par `npm run generate:api` depuis `backend/openapi.json`, et n'est jamais modifié à la main. La CI régénère les deux fichiers et échoue si le résultat diffère de ce qui est committé.

## Conséquences

Un changement de contrat casse le build du dashboard au lieu de casser l'affichage une fois en ligne. Le job frontend dépend du job backend, qui lui transmet le contrat exporté.

Effet de bord inattendu et bénéfique : la génération a révélé que le contrat était plus lâche que la réalité — les statuts y étaient déclarés en texte libre et le diff de schéma en objet quelconque. Le contrat a été resserré en conséquence (statuts énumérés, diff de schéma décrit champ par champ), ce qui profite autant à Swagger qu'au dashboard.
