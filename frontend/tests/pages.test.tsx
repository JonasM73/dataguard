import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { DatasetPage } from '../src/pages/DatasetPage'
import { Overview } from '../src/pages/Overview'
import { RunPage } from '../src/pages/RunPage'
import { failedRun } from './fixtures'
import { renderAt } from './render'
import { BASE, server } from './server'

describe('Overview', () => {
  it('affiche un état de chargement puis les datasets', async () => {
    renderAt(<Overview />)
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(await screen.findByText('Prix des carburants')).toBeInTheDocument()
    expect(screen.getByText('alerte')).toBeInTheDocument()
  })

  it("propose la démonstration quand aucun dataset n'est suivi", async () => {
    server.use(http.get(`${BASE}/datasets`, () => HttpResponse.json([])))
    renderAt(<Overview />)
    expect(await screen.findByText('Aucun dataset suivi')).toBeInTheDocument()
  })

  it("affiche l'erreur renvoyée par l'API", async () => {
    server.use(
      http.get(`${BASE}/datasets`, () =>
        HttpResponse.json(
          { error: { code: 'internal_error', message: 'Erreur interne.', details: null } },
          { status: 500 },
        ),
      ),
    )
    renderAt(<Overview />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Erreur interne.')
  })
})

describe('DatasetPage', () => {
  it("liste l'historique des exécutions", async () => {
    renderAt(<DatasetPage />, { path: '/datasets/:datasetId', route: '/datasets/ds-1' })
    await waitFor(() => expect(screen.getByText(/Historique des exécutions/)).toBeInTheDocument())
    expect(screen.getAllByText(/1000 lignes/)).toHaveLength(2)
  })

  it("permet de lancer une exécution", async () => {
    renderAt(<DatasetPage />, { path: '/datasets/:datasetId', route: '/datasets/ds-1' })
    expect(await screen.findByRole('button', { name: /Lancer une exécution/ })).toBeEnabled()
  })
})

describe('RunPage', () => {
  it('montre le score, les contrôles et la comparaison', async () => {
    renderAt(<RunPage />, { path: '/runs/:runId', route: '/runs/run-2' })
    expect(await screen.findByText(/91\.18/)).toBeInTheDocument()
    expect(screen.getByText('Contrôles')).toBeInTheDocument()
    expect(screen.getByText("Depuis l'exécution précédente")).toBeInTheDocument()
  })

  it("montre le message d'erreur d'un run échoué, sans score", async () => {
    server.use(http.get(`${BASE}/runs/:id`, () => HttpResponse.json(failedRun)))
    renderAt(<RunPage />, { path: '/runs/:runId', route: '/runs/run-failed' })
    expect(await screen.findByRole('alert')).toHaveTextContent('empty_file')
    // Un run techniquement échoué n'affiche aucun score : ni chiffre, ni « /100 ».
    expect(screen.queryByText('/100')).not.toBeInTheDocument()
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })
})
