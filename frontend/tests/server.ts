import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { dataset, runDetail, runSummaries } from './fixtures'

const BASE = 'http://localhost:8000/api/v1'

export const handlers = [
  http.get(`${BASE}/datasets`, () => HttpResponse.json([dataset])),
  http.get(`${BASE}/datasets/:id/runs`, () => HttpResponse.json(runSummaries)),
  http.get(`${BASE}/runs/:id`, () => HttpResponse.json(runDetail)),
  http.post(`${BASE}/runs`, () => HttpResponse.json(runDetail, { status: 201 })),
]

export const server = setupServer(...handlers)
export { BASE }
