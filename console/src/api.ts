export type Team = { team_id: string; name: string; allowed_models: string[]; rate_limits: { requests_per_minute: number; tokens_per_minute: number }; budgets: { daily_usd: number; monthly_usd: number } }
export type Usage = { team_id: string; tokens_this_minute: number; spend: { daily_usd: number; monthly_usd: number }; budgets: Team['budgets']; rate_limits: Team['rate_limits'] }
export type Provider = { provider: string; model: string; circuit_state: string; recent_failures: number; last_failure_at: number | null }
export type Capabilities = { version: string; provider_mode: string; providers: string[]; pricing: Record<string, { input_price_per_1k: number; output_price_per_1k: number }>; dev_controls: boolean; streaming: boolean; real_providers: boolean; usage_history: boolean; config_mutation: boolean }
import type { components } from './generated/api'
export type Chat = components['schemas']['ChatCompletionResponse']
export type Message = components['schemas']['ChatMessage']

export class ApiError extends Error {
  constructor(public status: number, message: string, public retryAfter?: string) { super(message) }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try { response = await fetch(path, init) } catch { throw new ApiError(0, 'Cannot reach the gateway. Check the running services.') }
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new ApiError(response.status, body.message || body.detail || response.statusText, response.headers.get('Retry-After') || undefined)
  return body as T
}

export const api = {
  ready: () => request<{ status: string; dependencies: { redis: string } }>('/ready'),
  capabilities: () => request<Capabilities>('/meta/capabilities'),
  teams: () => request<{ teams: Team[] }>('/admin/teams'),
  usage: (id: string) => request<Usage>(`/admin/teams/${encodeURIComponent(id)}/usage`),
  providers: () => request<{ providers: Provider[] }>('/providers/health'),
  chat: async (key: string, model: string, messages: Message[]) => {
    const start = performance.now()
    let response: Response
    try { response = await fetch('/v1/chat/completions', { method: 'POST', headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ model, messages }) }) }
    catch { throw new ApiError(0, 'Cannot reach the gateway. Check the running services.') }
    const body = await response.json().catch(() => ({}))
    if (!response.ok) throw new ApiError(response.status, body.message || body.detail || response.statusText, response.headers.get('Retry-After') || undefined)
    return { body: body as Chat, requestId: response.headers.get('X-Request-ID'), latencyMs: Math.round(performance.now() - start) }
  },
  dev: <T>(token: string, path: string, body?: unknown) => request<T>(`/dev${path}`, { method: body === undefined ? 'GET' : 'POST', headers: { 'X-Dev-Control-Token': token, 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) }),
}

export function errorText(error: unknown): string {
  if (!(error instanceof ApiError)) return error instanceof Error ? error.message : 'Unexpected error'
  const labels: Record<number, string> = { 401: 'Invalid or missing API key', 402: 'Budget exhausted', 403: 'Model or action not allowed', 429: 'Request rate limit reached', 502: 'Provider error', 503: 'Provider or dependency unavailable' }
  return `${labels[error.status] || 'Request failed'}: ${error.message}${error.retryAfter ? ` Retry in ${error.retryAfter}s.` : ''}`
}
