import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { CheckList } from '../components/CheckList'
import { ComparisonPanel } from '../components/ComparisonPanel'
import { ErrorState, Loading } from '../components/States'
import { Score } from '../components/Score'
import { StatusBadge } from '../components/StatusBadge'

export function RunPage() {
  const { runId = '' } = useParams()
  const { data, isPending, error, refetch } = useQuery({
    queryKey: ['run', runId],
    queryFn: () => api.run(runId),
    enabled: Boolean(runId),
  })

  if (isPending) return <Loading />
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />

  return (
    <div className="space-y-4">
      <div>
        <Link to={`/datasets/${data.dataset_id}`} className="text-sm text-slate-500 hover:underline">
          ← Historique du dataset
        </Link>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <Score value={data.score} size="lg" />
          <StatusBadge status={data.status} />
          <a
            href={api.reportUrl(data.id)}
            className="ml-auto rounded border px-3 py-1.5 text-sm hover:bg-slate-100"
          >
            Télécharger le rapport
          </a>
        </div>
      </div>

      {data.error_message && (
        <div className="rounded border border-red-300 bg-red-50 p-4" role="alert">
          <p className="font-medium text-red-800">L'ingestion a échoué</p>
          <p className="mt-1 font-mono text-sm text-red-700">{data.error_message}</p>
        </div>
      )}

      <dl className="grid grid-cols-2 gap-3 rounded border bg-white p-4 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-slate-500">Lignes</dt>
          <dd className="tabular-nums">{data.rows_read ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Colonnes</dt>
          <dd className="tabular-nums">{data.columns_read ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Durée</dt>
          <dd className="tabular-nums">{data.duration_ms ?? '—'} ms</dd>
        </div>
        <div>
          <dt className="text-slate-500">Fraîcheur</dt>
          <dd>
            {data.freshness.date === null || data.freshness.age_hours === null
              ? 'non mesurée'
              : data.freshness.age_hours < 0
                ? `${Math.abs(data.freshness.age_hours)} h dans le futur (${data.freshness.origin})`
                : `${data.freshness.age_hours} h (${data.freshness.origin})`}
          </dd>
        </div>
      </dl>

      {data.results.length > 0 && (
        <section>
          <h2 className="mb-2 font-semibold">Contrôles</h2>
          <CheckList results={data.results} />
          <p className="mt-2 text-sm text-slate-500">
            Le score est la moyenne des contrôles exécutés, pondérée par leur poids. Les contrôles
            non applicables en sont exclus.
          </p>
        </section>
      )}

      {data.comparison && <ComparisonPanel comparison={data.comparison} />}
    </div>
  )
}
