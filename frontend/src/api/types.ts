/**
 * Types du contrat d'API.
 *
 * `schema.d.ts` est produit par `npm run generate:api` depuis le contrat
 * OpenAPI du backend ; il n'est jamais modifié à la main. Ce fichier ne fait
 * qu'en extraire des alias lisibles. La CI régénère le fichier et échoue si le
 * résultat diffère de ce qui est committé : un changement de contrat casse
 * ainsi le build plutôt que l'affichage une fois en ligne.
 */

import type { components } from './schema'

type Schemas = components['schemas']

export type Source = Schemas['SourceOut']
export type LastRun = Schemas['LastRunSummary']
export type DatasetSummary = Schemas['DatasetSummary']
export type DatasetDetail = Schemas['DatasetOut']
export type QualityResult = Schemas['QualityResultOut']
export type SchemaField = Schemas['SchemaFieldOut']
export type RunComparison = Schemas['RunComparisonOut']
export type RunSummary = Schemas['RunSummary']
export type RunDetail = Schemas['RunDetail']
export type Page<T> = { items: T[]; total: number; limit: number; offset: number }
export type SchemaDiff = Schemas['SchemaDiff']
export type CheckDiff = Schemas['CheckDiff']

/**
 * Les quatre statuts, tels que le contrat les déclare. Le dashboard doit les
 * traiter tous les quatre, et le compilateur le vérifie.
 */
export type CheckStatus = NonNullable<QualityResult['status']>

export interface ApiError {
  error: { code: string; message: string; details: unknown }
}
