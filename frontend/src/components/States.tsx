import { ApiFailure } from '../api/client'

export function Loading({ label = 'Chargement…' }: { label?: string }) {
  return (
    <div className="animate-pulse py-10 text-center text-slate-500" role="status">
      {label}
    </div>
  )
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded border border-dashed border-slate-300 py-10 text-center">
      <p className="font-medium text-slate-700">{title}</p>
      {hint && <p className="mt-1 text-sm text-slate-500">{hint}</p>}
    </div>
  )
}

/**
 * Une erreur affiche ce qui s'est passé et ce qu'on peut faire ensuite ;
 * un simple « une erreur est survenue » laisserait l'utilisateur sans recours.
 */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const failure = error instanceof ApiFailure ? error : null
  const message = failure?.message ?? 'Erreur inattendue.'
  const hint =
    failure?.code === 'network_error'
      ? "Vérifiez que l'API est démarrée (docker compose up)."
      : failure?.code

  return (
    <div className="rounded border border-red-300 bg-red-50 p-4" role="alert">
      <p className="font-medium text-red-800">{message}</p>
      {hint && <p className="mt-1 text-sm text-red-700">{hint}</p>}
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-3 rounded border border-red-300 bg-white px-3 py-1 text-sm hover:bg-red-100"
        >
          Réessayer
        </button>
      )}
    </div>
  )
}
