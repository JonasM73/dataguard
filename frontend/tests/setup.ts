import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { server } from './server'

// jsdom n'implémente pas ResizeObserver, dont Recharts se sert pour
// dimensionner ses graphiques. Sans ce bouchon, toute page contenant une
// courbe fait échouer le test pour une raison étrangère à ce qu'il vérifie.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver

// L'API est simulée : aucun test frontend ne démarre le backend, et aucun ne
// dépend d'une base de données.
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
})
afterAll(() => server.close())
