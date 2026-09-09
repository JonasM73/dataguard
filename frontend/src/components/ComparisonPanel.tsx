import type { RunComparison } from '../api/types'
import { Delta } from './Score'

/**
 * La comparaison répond à la seconde question du projet : « qu'est-ce qui a
 * changé depuis la dernière fois ? » Un score qui baisse sans explication
 * n'apprend rien à personne.
 */
export function ComparisonPanel({ comparison }: { comparison: RunComparison }) {
  const { schema_diff: schema, checks_diff: checks } = comparison
  const schemaChanged =
    schema.added.length + schema.removed.length + schema.renamed.length + schema.type_changed.length

  return (
    <section className="rounded border bg-white p-4">
      <h2 className="mb-3 font-semibold">Depuis l'exécution précédente</h2>

      <dl className="mb-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-slate-500">Lignes</dt>
          <dd>
            <Delta value={comparison.rows_delta} />
            {comparison.rows_delta_pct !== null && comparison.rows_delta !== 0 && (
              <span className="ml-1 text-slate-500">({comparison.rows_delta_pct} %)</span>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Score</dt>
          <dd>
            <Delta value={comparison.score_delta} />
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Schéma</dt>
          <dd>{schemaChanged === 0
              ? 'identique'
              : `${schemaChanged} différence${schemaChanged > 1 ? 's' : ''}`}</dd>
        </div>
      </dl>

      {schemaChanged > 0 && (
        <ul className="mb-3 space-y-1 text-sm">
          {schema.removed.map((c) => (
            <li key={`r-${c}`} className="text-red-700">
              colonne supprimée : <code>{c}</code>
            </li>
          ))}
          {schema.renamed.map((r) => (
            <li key={`n-${r.from}`} className="text-red-700">
              renommée : <code>{r.from}</code> → <code>{r.to}</code>
            </li>
          ))}
          {schema.type_changed.map((t) => (
            <li key={`t-${t.column}`} className="text-red-700">
              type changé : <code>{t.column}</code> ({t.from} → {t.to})
            </li>
          ))}
          {schema.added.map((c) => (
            <li key={`a-${c}`} className="text-amber-800">
              colonne ajoutée : <code>{c}</code>
            </li>
          ))}
        </ul>
      )}

      {checks.length > 0 && (
        <ul className="space-y-1 text-sm">
          {checks.map((change) => (
            <li key={change.check_name}>
              <code>{change.check_name}</code> : {change.from ?? 'absent'} → {change.to ?? 'absent'}
            </li>
          ))}
        </ul>
      )}

      {schemaChanged === 0 && checks.length === 0 && (
        <p className="text-sm text-slate-600">Aucun changement détecté.</p>
      )}
    </section>
  )
}
