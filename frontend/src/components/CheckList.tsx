import { useState } from 'react'
import type { QualityResult } from '../api/types'
import { StatusBadge } from './StatusBadge'

/**
 * Le détail d'un contrôle est repliable : on montre d'abord ce qui ne va pas,
 * puis, à la demande, sur quelles colonnes et avec quelles valeurs. Tout
 * dérouler d'emblée noierait le signal.
 */
function Details({ result }: { result: QualityResult }) {
  const details = result.details as {
    columns?: { column: string; status?: string; sample_values?: unknown[]; [k: string]: unknown }[]
    added?: string[]
    removed?: string[]
    renamed?: { from: string; to: string }[]
    type_changed?: { column: string; from: string; to: string }[]
    reason?: string
    age_hours?: number
    origin?: string
    configured_columns?: number
    checked_columns?: number
    missing_columns?: string[]
    source_columns?: string[]
    [k: string]: unknown
  }

  if (details.reason) return <p className="text-sm text-slate-600">{details.reason}</p>

  return (
    <div className="space-y-2 text-sm">
      {partialCoverage(details) && (
        <p className="rounded border border-amber-300 bg-amber-50 p-2 text-amber-900">
          {details.checked_columns} colonne(s) contrôlée(s) sur {details.configured_columns}{' '}
          configurée(s). Absentes du fichier :{' '}
          <span className="font-mono text-xs">{details.missing_columns!.join(', ')}</span>.
          Le verdict ci-dessus ne porte que sur les colonnes trouvées.
        </p>
      )}
      {details.origin && (
        <div className="space-y-1 text-slate-600">
          <p>
            Provenance de la date : <span className="font-medium">{details.origin}</span>
            {details.age_hours !== undefined && (
              <>
                {' — '}
                {details.age_hours < 0
                  ? `datée de ${Math.abs(details.age_hours)} h dans le futur`
                  : `ancienneté ${details.age_hours} h`}
              </>
            )}
          </p>
          {details.age_hours !== undefined && details.age_hours < 0 && (
            <p className="text-amber-800">
              Une donnée postérieure à l'instant de l'ingestion reste fraîche au sens de ce
              contrôle ; c'est la cohérence qui juge de sa vraisemblance.
            </p>
          )}
          {(details.source_columns?.length ?? 0) > 0 && (
            <p className="font-mono text-xs">{details.source_columns!.join(', ')}</p>
          )}
        </div>
      )}
      {(details.removed?.length ?? 0) > 0 && (
        <p className="text-red-700">Colonnes supprimées : {details.removed!.join(', ')}</p>
      )}
      {(details.added?.length ?? 0) > 0 && (
        <p className="text-amber-800">Colonnes ajoutées : {details.added!.join(', ')}</p>
      )}
      {(details.renamed?.length ?? 0) > 0 && (
        <p className="text-red-700">
          Renommées : {details.renamed!.map((r) => `${r.from} → ${r.to}`).join(', ')}
        </p>
      )}
      {(details.type_changed?.length ?? 0) > 0 && (
        <p className="text-red-700">
          Types changés :{' '}
          {details.type_changed!.map((t) => `${t.column} (${t.from} → ${t.to})`).join(', ')}
        </p>
      )}
      {(details.columns?.length ?? 0) > 0 && (
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b text-xs uppercase text-slate-500">
              <th className="py-1">Colonne</th>
              <th className="py-1">Mesure</th>
              <th className="py-1">Exemples</th>
            </tr>
          </thead>
          <tbody>
            {details.columns!.map((column) => (
              <tr key={column.column} className="border-b last:border-0">
                <td className="py-1 font-mono text-xs">{column.column}</td>
                <td className="py-1 tabular-nums">
                  {(column.null_pct as number) ?? (column.invalid_pct as number) ?? '—'} %
                </td>
                <td className="py-1 font-mono text-xs text-slate-600">
                  {(column.sample_values as unknown[] | undefined)?.slice(0, 3).join(', ') ?? '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

/**
 * Un contrôle qui n'a pas trouvé les colonnes qu'on lui avait désignées n'a pas
 * « rien à signaler » : il n'a pas regardé grand-chose. L'écrire noir sur blanc
 * évite le pire des faux acquittements, celui qui affiche « conforme » sur un
 * fichier dont toutes les colonnes ont changé de nom.
 */
function partialCoverage(details: {
  configured_columns?: number
  checked_columns?: number
  missing_columns?: string[]
}): boolean {
  return (
    details.configured_columns !== undefined &&
    details.checked_columns !== undefined &&
    details.checked_columns < details.configured_columns
  )
}

/**
 * Les unités sont écrites au pluriel côté moteur ; on les accorde à l'affichage
 * plutôt que de faire porter la grammaire française à une clé de données.
 */
function unitLabel(result: QualityResult): string {
  const unit = (result.details.unit as string) ?? ''
  if (result.failed_count !== 1) return unit
  return unit
    .replace(/^différences/, 'différence')
    .replace(/^colonnes/, 'colonne')
    .replace(/^lignes/, 'ligne')
    .replace(/^valeurs/, 'valeur')
    .replace(/ en défaut$/, ' en défaut')
}

export function CheckList({ results }: { results: QualityResult[] }) {
  const [open, setOpen] = useState<string | null>(null)

  return (
    <ul className="divide-y rounded border bg-white">
      {results.map((result) => {
        const expanded = open === result.check_name
        return (
          <li key={result.check_name}>
            <button
              onClick={() => setOpen(expanded ? null : result.check_name)}
              className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-slate-50"
              aria-expanded={expanded}
            >
              <StatusBadge status={result.status} />
              <span className="flex-1 font-medium">{result.dimension}</span>
              <span className="text-sm text-slate-500">poids {result.weight}</span>
              {partialCoverage(result.details) && (
                <span
                  className="rounded border border-amber-300 bg-amber-50 px-1.5 py-0.5 text-xs text-amber-900"
                  title="Des colonnes désignées par la configuration sont absentes du fichier"
                >
                  {result.details.checked_columns as number}/
                  {result.details.configured_columns as number} colonnes
                </span>
              )}
              {result.failed_count > 0 && (
                <span className="text-sm tabular-nums text-slate-700">
                  {result.failed_count} {unitLabel(result)}
                </span>
              )}
              <span className="text-slate-400">{expanded ? '−' : '+'}</span>
            </button>
            {expanded && (
              <div className="border-t bg-slate-50 px-4 py-3">
                <Details result={result} />
              </div>
            )}
          </li>
        )
      })}
    </ul>
  )
}
