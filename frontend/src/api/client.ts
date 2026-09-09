/**
 * Client HTTP.
 *
 * Toutes les erreurs de l'API arrivent sous la même forme `{error: {...}}` :
 * on les convertit ici en une exception unique, de sorte que l'affichage n'ait
 * qu'un seul cas d'erreur à traiter.
 */

import type { ApiError, DatasetSummary, Page, RunDetail, RunSummary } from './types'

const BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

export class ApiFailure extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'ApiFailure'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, init)
  } catch {
    // Panne réseau : le message générique du navigateur n'aiderait personne.
    throw new ApiFailure('network_error', "L'API est injoignable.", 0)
  }

  if (response.status === 204) return undefined as T

  if (!response.ok) {
    let code = 'unknown_error'
    let message = `Erreur ${response.status}`
    try {
      const body = (await response.json()) as ApiError
      code = body.error?.code ?? code
      message = body.error?.message ?? message
    } catch {
      // Corps illisible : on garde le message construit sur le code HTTP.
    }
    throw new ApiFailure(code, message, response.status)
  }
  return (await response.json()) as T
}

export const api = {
  health: () => request<{ status: string; database: string }>('/health'),
  datasets: () => request<DatasetSummary[]>('/datasets'),
  runs: (datasetId: string, limit = 20, offset = 0) =>
    request<Page<RunSummary>>(`/datasets/${datasetId}/runs?limit=${limit}&offset=${offset}`),
  run: (runId: string) => request<RunDetail>(`/runs/${runId}`),
  launch: (datasetId: string) =>
    request<RunDetail>('/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dataset_id: datasetId }),
    }),
  reportUrl: (runId: string) => `${BASE}/runs/${runId}/report`,
}
