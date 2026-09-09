import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ComparisonPanel } from '../src/components/ComparisonPanel'
import { CheckList } from '../src/components/CheckList'
import { Score } from '../src/components/Score'
import { StatusBadge } from '../src/components/StatusBadge'
import { ErrorState } from '../src/components/States'
import { ApiFailure } from '../src/api/client'
import { tickFormat } from '../src/pages/DatasetPage'
import { runDetail } from './fixtures'

describe('StatusBadge', () => {
  it('écrit le statut au lieu de le coder par la seule couleur', () => {
    render(<StatusBadge status="failed" />)
    expect(screen.getByText('échec')).toBeInTheDocument()
  })
})

describe('Score', () => {
  it('affiche la valeur', () => {
    render(<Score value={91.18} />)
    expect(screen.getByText(/91\.18/)).toBeInTheDocument()
  })

  it("n'affiche pas zéro quand rien n'a été mesuré", () => {
    render(<Score value={null} />)
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.queryByText(/^0/)).not.toBeInTheDocument()
  })
})

describe('CheckList', () => {
  it('liste les contrôles avec leur statut et leur poids', () => {
    render(<CheckList results={runDetail.results} />)
    expect(screen.getByText('Schéma')).toBeInTheDocument()
    expect(screen.getByText('Complétude')).toBeInTheDocument()
    expect(screen.getByText('poids 3')).toBeInTheDocument()
  })

  it('ne déroule le détail que sur demande', async () => {
    render(<CheckList results={runDetail.results} />)
    expect(screen.queryByText(/services_v2/)).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Schéma/ }))
    expect(screen.getByText(/services_v2/)).toBeInTheDocument()
  })

  it('signale un contrôle qui n\'a pas trouvé toutes ses colonnes', async () => {
    render(<CheckList results={runDetail.results} />)
    // Visible sans déplier : « conforme » seul serait un faux acquittement.
    expect(screen.getByText('7/17 colonnes')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Complétude/ }))
    expect(screen.getByText(/Absentes du fichier/)).toBeInTheDocument()
    expect(screen.getByText(/Code postal, Ville, Prix Gazole/)).toBeInTheDocument()
  })

  it('ne montre aucun badge de couverture quand tout a été contrôlé', () => {
    render(
      <CheckList
        results={[
          {
            ...runDetail.results[1]!,
            details: { configured_columns: 17, checked_columns: 17, missing_columns: [] },
          },
        ]}
      />,
    )
    expect(screen.queryByText(/17\/17 colonnes/)).not.toBeInTheDocument()
  })

  it('présente la fraîcheur sans tableau vide, et dit le futur en clair', async () => {
    render(<CheckList results={runDetail.results} />)
    await userEvent.click(screen.getByRole('button', { name: /Fraîcheur/ }))
    expect(screen.getByText(/1.58 h dans le futur/)).toBeInTheDocument()
    expect(screen.getByText(/c'est la cohérence qui juge/)).toBeInTheDocument()
    // Les colonnes sources sont des noms, pas des lignes de tableau.
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it("explique pourquoi un contrôle n'est pas applicable", async () => {
    render(<CheckList results={runDetail.results} />)
    await userEvent.click(screen.getByRole('button', { name: /Volume/ }))
    expect(screen.getByText(/aucune exécution précédente/)).toBeInTheDocument()
  })
})

describe('ComparisonPanel', () => {
  it('nomme la colonne ajoutée et le contrôle qui a changé', () => {
    render(<ComparisonPanel comparison={runDetail.comparison!} />)
    expect(screen.getByText(/colonne ajoutée/)).toBeInTheDocument()
    expect(screen.getByText('services_v2')).toBeInTheDocument()
    expect(screen.getByText(/success → warning/)).toBeInTheDocument()
  })

  it('dit explicitement quand rien ne change', () => {
    render(
      <ComparisonPanel
        comparison={{
          previous_run_id: 'x', rows_delta: 0, rows_delta_pct: 0, score_delta: 0,
          schema_diff: { added: [], removed: [], renamed: [], type_changed: [] },
          checks_diff: [],
        }}
      />,
    )
    expect(screen.getByText('Aucun changement détecté.')).toBeInTheDocument()
  })
})

describe('ErrorState', () => {
  it("oriente l'utilisateur quand l'API est injoignable", () => {
    render(<ErrorState error={new ApiFailure('network_error', "L'API est injoignable.", 0)} />)
    expect(screen.getByRole('alert')).toHaveTextContent("L'API est injoignable.")
    expect(screen.getByText(/docker compose up/)).toBeInTheDocument()
  })
})

describe('tickFormat', () => {
  const at = (iso: string) => ({ started_at: iso })

  it('descend à la seconde quand les exécutions se suivent de près', () => {
    // Sans cela, cinq exécutions d'une même minute portent cinq étiquettes
    // identiques et l'axe ne distingue plus rien.
    const f = tickFormat([at('2026-09-09T04:46:35Z'), at('2026-09-09T04:46:41Z')])
    expect(f.second).toBe('2-digit')
    expect(f.day).toBeUndefined()
  })

  it('garde date et heure sur un historique de quelques heures', () => {
    const f = tickFormat([at('2026-09-08T08:00:00Z'), at('2026-09-09T20:00:00Z')])
    expect(f.day).toBe('2-digit')
    expect(f.hour).toBe('2-digit')
    expect(f.second).toBeUndefined()
  })

  it("s'en tient au jour sur un historique long", () => {
    const f = tickFormat([at('2026-01-01T00:00:00Z'), at('2026-09-09T00:00:00Z')])
    expect(f.day).toBe('2-digit')
    expect(f.hour).toBeUndefined()
  })

  it('reste lisible avec une seule exécution', () => {
    expect(tickFormat([at('2026-09-09T04:46:35Z')]).day).toBe('2-digit')
  })
})

describe('accord du singulier', () => {
  it('écrit « 1 différence » et non « 1 différences »', () => {
    render(
      <CheckList
        results={[
          {
            ...runDetail.results[0]!,
            failed_count: 1,
            details: { unit: 'différences de schéma' },
          },
        ]}
      />,
    )
    expect(screen.getByText('1 différence de schéma')).toBeInTheDocument()
  })

  it('conserve le pluriel au-delà de un', () => {
    render(
      <CheckList
        results={[
          {
            ...runDetail.results[0]!,
            failed_count: 3,
            details: { unit: 'différences de schéma' },
          },
        ]}
      />,
    )
    expect(screen.getByText('3 différences de schéma')).toBeInTheDocument()
  })
})
