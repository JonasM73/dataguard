import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { Empty, ErrorState, Loading } from '../components/States'
import { Score } from '../components/Score'
import { StatusBadge } from '../components/StatusBadge'

export function Overview() {
  const { data, isPending, error, refetch } = useQuery({
    queryKey: ['datasets'],
    queryFn: api.datasets,
  })

  if (isPending) return <Loading label="Chargement des datasets…" />
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />
  if (data.length === 0)
    return (
      <Empty
        title="Aucun dataset suivi"
        hint="Créez-en un via l'API, ou lancez « make demo » pour la démonstration."
      />
    )

  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-semibold">Datasets suivis</h1>
      <ul className="grid gap-3 sm:grid-cols-2">
        {data.map((dataset) => (
          <li key={dataset.id}>
            <Link
              to={`/datasets/${dataset.id}`}
              className="block rounded border bg-white p-4 hover:border-slate-400"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-medium">{dataset.name}</p>
                  <p className="truncate text-sm text-slate-500">{dataset.source.name}</p>
                </div>
                <Score value={dataset.last_run?.score ?? null} size="sm" />
              </div>
              <div className="mt-3 flex items-center gap-2 text-sm text-slate-600">
                {dataset.last_run ? (
                  <>
                    <StatusBadge status={dataset.last_run.status} />
                    <span>{new Date(dataset.last_run.started_at).toLocaleString('fr-FR')}</span>
                  </>
                ) : (
                  <span className="text-slate-500">jamais exécuté</span>
                )}
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
