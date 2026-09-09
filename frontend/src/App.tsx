import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { DatasetPage } from './pages/DatasetPage'
import { Overview } from './pages/Overview'
import { RunPage } from './pages/RunPage'

// Les données de qualité ne changent qu'à l'exécution d'un run : les
// rafraîchir au moindre retour sur l'onglet n'apporterait rien.
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 30_000 } },
})

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-3">
          <Link to="/" className="font-semibold">
            DataGuard
          </Link>
          <span className="text-sm text-slate-500">qualité des données publiques</span>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
    </div>
  )
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Shell>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/datasets/:datasetId" element={<DatasetPage />} />
            <Route path="/runs/:runId" element={<RunPage />} />
          </Routes>
        </Shell>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
