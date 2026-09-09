import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { api } from '../api/client'
import { Empty, ErrorState, Loading } from '../components/States'
import { Score } from '../components/Score'
import { StatusBadge } from '../components/StatusBadge'

/**
 * Granularité des étiquettes de l'axe, choisie sur l'écart réel entre la
 * première et la dernière exécution.
 *
 * Une échelle fixe se trompe dans les deux sens : cinq exécutions lancées dans
 * la même minute donnent cinq étiquettes « 09/09 04:46 » indistinctes, tandis
 * qu'une heure seule ne veut plus rien dire sur un historique d'un an.
 */
export function tickFormat(runs: { started_at: string }[]): Intl.DateTimeFormatOptions {
  if (runs.length < 2) return { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }
  const first = new Date(runs[0]!.started_at).getTime()
  const last = new Date(runs[runs.length - 1]!.started_at).getTime()
  const span = Math.abs(last - first)

  const HEURE = 3_600_000
  const JOUR = 24 * HEURE
  if (span < 2 * HEURE) return { hour: '2-digit', minute: '2-digit', second: '2-digit' }
  if (span < 3 * JOUR) return { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }
  return { day: '2-digit', month: '2-digit' }
}

export function DatasetPage() {
  const { datasetId = '' } = useParams()
  const queryClient = useQueryClient()

  const datasets = useQuery({ queryKey: ['datasets'], queryFn: api.datasets })
  const runs = useQuery({
    queryKey: ['runs', datasetId],
    queryFn: () => api.runs(datasetId, 50),
    enabled: Boolean(datasetId),
  })

  const launch = useMutation({
    mutationFn: () => api.launch(datasetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runs', datasetId] })
      queryClient.invalidateQueries({ queryKey: ['datasets'] })
    },
  })

  const dataset = datasets.data?.find((d) => d.id === datasetId)

  if (runs.isPending) return <Loading />
  if (runs.error) return <ErrorState error={runs.error} onRetry={() => runs.refetch()} />

  // Du plus ancien au plus récent : une courbe se lit dans le sens du temps.
  // Les exécutions sans score — celles qui ont échoué à l'ingestion — sont
  // écartées : les tracer à zéro laisserait croire à une qualité nulle.
  const scored = [...runs.data.items].reverse().filter((run) => run.score !== null)
  const history = scored.map((run) => ({
    date: new Date(run.started_at).toLocaleString('fr-FR', tickFormat(scored)),
    score: run.score,
  }))

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link to="/" className="text-sm text-slate-500 hover:underline">
            ← Tous les datasets
          </Link>
          <h1 className="text-2xl font-semibold">{dataset?.name ?? 'Dataset'}</h1>
        </div>
        <button
          onClick={() => launch.mutate()}
          disabled={launch.isPending}
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          {launch.isPending ? 'Exécution en cours…' : 'Lancer une exécution'}
        </button>
      </div>

      {launch.error && <ErrorState error={launch.error} />}

      {history.length > 1 && (
        <section className="rounded border bg-white p-4">
          <h2 className="font-semibold">Évolution du score</h2>
          <p className="mb-3 text-sm text-slate-500">
            Un point par exécution. Le détail chiffré de chacune figure dans
            l'historique ci-dessous.
          </p>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history} margin={{ top: 8, right: 16, bottom: 4, left: -8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                {/* minTickGap évite de répéter le même horodatage quand plusieurs
                    exécutions se suivent de près. */}
                <XAxis
                  dataKey="date"
                  fontSize={11}
                  stroke="#94a3b8"
                  tickLine={false}
                  minTickGap={48}
                />
                {/* Échelle ancrée à zéro : un score est borné, tronquer l'axe
                    exagérerait visuellement des écarts de quelques points. */}
                <YAxis
                  domain={[0, 100]}
                  ticks={[0, 25, 50, 75, 100]}
                  fontSize={11}
                  stroke="#94a3b8"
                  tickLine={false}
                  axisLine={false}
                  width={36}
                />
                <Tooltip
                  formatter={(value: number | string) => [`${value} / 100`, 'Score']}
                  labelFormatter={(label: string) => `Exécution du ${label}`}
                  contentStyle={{ fontSize: 12, borderRadius: 6, borderColor: '#cbd5e1' }}
                />
                {/* Interpolation linéaire, et non lissée : une spline dessinerait
                    entre deux exécutions des valeurs qui n'ont jamais été mesurées. */}
                <Line
                  type="linear"
                  dataKey="score"
                  stroke="#0f172a"
                  strokeWidth={2}
                  dot={
                    history.length <= 30
                      ? { r: 4, fill: '#0f172a', stroke: '#ffffff', strokeWidth: 2 }
                      : false
                  }
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      <section>
        <h2 className="mb-2 font-semibold">Historique des exécutions ({runs.data.total})</h2>
        {runs.data.items.length === 0 ? (
          <Empty title="Aucune exécution" hint="Lancez-en une avec le bouton ci-dessus." />
        ) : (
          <ul className="divide-y rounded border bg-white">
            {runs.data.items.map((run) => (
              <li key={run.id}>
                <Link
                  to={`/runs/${run.id}`}
                  className="flex flex-wrap items-center gap-3 px-4 py-3 hover:bg-slate-50"
                >
                  <StatusBadge status={run.status} />
                  <span className="flex-1 text-sm">
                    {new Date(run.started_at).toLocaleString('fr-FR')}
                  </span>
                  <span className="text-sm tabular-nums text-slate-500">
                    {run.rows_read ?? '—'} lignes
                  </span>
                  <span className="text-sm tabular-nums text-slate-500">
                    {run.duration_ms ?? '—'} ms
                  </span>
                  <Score value={run.score} size="sm" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
