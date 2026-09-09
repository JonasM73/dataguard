import type { CheckStatus } from '../api/types'

const LABELS: Record<CheckStatus, string> = {
  success: 'conforme',
  warning: 'alerte',
  failed: 'échec',
  skipped: 'non applicable',
}

const STYLES: Record<CheckStatus, string> = {
  success: 'bg-green-100 text-green-800 border-green-300',
  warning: 'bg-amber-100 text-amber-900 border-amber-300',
  failed: 'bg-red-100 text-red-800 border-red-300',
  skipped: 'bg-slate-100 text-slate-600 border-slate-300',
}

/**
 * Le statut est toujours écrit, jamais seulement coloré : un badge qui ne se
 * distingue que par sa teinte est illisible pour une partie des lecteurs.
 */
export function StatusBadge({ status }: { status: CheckStatus }) {
  return (
    <span
      className={`inline-block rounded border px-2 py-0.5 text-xs font-medium ${STYLES[status]}`}
      data-testid={`status-${status}`}
    >
      {LABELS[status]}
    </span>
  )
}

export function statusLabel(status: CheckStatus): string {
  return LABELS[status]
}
