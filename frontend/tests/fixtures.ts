import type { DatasetSummary, Page, RunDetail, RunSummary } from '../src/api/types'

export const source = {
  id: 'src-1',
  name: 'data.economie.gouv.fr',
  url: 'https://example.org/prix.csv',
  format: 'csv',
  license: 'Licence Ouverte 2.0',
  created_at: '2026-09-01T10:00:00Z',
}

export const dataset: DatasetSummary = {
  id: 'ds-1',
  name: 'Prix des carburants',
  description: null,
  expected_frequency: 'P1D',
  active: true,
  source,
  last_run: { id: 'run-2', started_at: '2026-09-09T10:00:00Z', status: 'warning', score: 91.18 },
}

export const runSummaries: Page<RunSummary> = {
  items: [
    {
      id: 'run-2', dataset_id: 'ds-1', started_at: '2026-09-09T10:00:00Z',
      finished_at: '2026-09-09T10:00:01Z', duration_ms: 120, status: 'warning',
      score: 91.18, rows_read: 1000, columns_read: 48, error_message: null,
    },
    {
      id: 'run-1', dataset_id: 'ds-1', started_at: '2026-09-09T09:00:00Z',
      finished_at: '2026-09-09T09:00:01Z', duration_ms: 118, status: 'success',
      score: 100, rows_read: 1000, columns_read: 47, error_message: null,
    },
  ],
  total: 2, limit: 20, offset: 0,
}

export const runDetail: RunDetail = {
  ...runSummaries.items[0]!,
  file_size_bytes: 777163,
  checksum: 'sha256:abc123',
  freshness: { date: '2026-09-09T09:45:00Z', origin: 'column', age_hours: 0.25 },
  results: [
    {
      check_name: 'schema', dimension: 'Schéma', status: 'warning', weight: 3, score: 0.5,
      failed_count: 1, threshold: {},
      details: { unit: 'différences de schéma', added: ['services_v2'], removed: [], renamed: [], type_changed: [] },
    },
    {
      check_name: 'completeness', dimension: 'Complétude', status: 'success', weight: 2, score: 1,
      failed_count: 0, threshold: {},
      // Couverture partielle : sept colonnes trouvées sur les dix-sept configurées.
      details: {
        unit: 'colonnes en défaut', columns: [],
        configured_columns: 17, checked_columns: 7,
        missing_columns: ['Code postal', 'Ville', 'Prix Gazole'],
      },
    },
    {
      check_name: 'freshness', dimension: 'Fraîcheur', status: 'success', weight: 2, score: 1,
      failed_count: 0, threshold: {},
      details: {
        unit: 'dataset', origin: 'column', age_hours: -1.58,
        source_columns: ['Prix Gazole mis à jour le', 'Prix SP95 mis à jour le'],
      },
    },
    {
      check_name: 'volume', dimension: 'Volume', status: 'skipped', weight: 1, score: 0,
      failed_count: 0, threshold: {}, details: { reason: 'aucune exécution précédente pour comparer' },
    },
  ],
  schema: [{ column_name: 'id', data_type: 'string', nullable: false, position: 0 }],
  comparison: {
    previous_run_id: 'run-1',
    rows_delta: 0,
    rows_delta_pct: 0,
    score_delta: -8.82,
    schema_diff: { added: ['services_v2'], removed: [], renamed: [], type_changed: [] },
    checks_diff: [{ check_name: 'schema', from: 'success', to: 'warning' }],
  },
}

export const failedRun: RunDetail = {
  ...runDetail,
  id: 'run-failed', status: 'failed', score: null, rows_read: null, columns_read: null,
  error_message: "[empty_file] Le fichier ne contient aucune ligne : il n'y a rien à contrôler.",
  results: [], comparison: null,
}
