import {
  PortfolioWeight,
  NavPoint,
  PortfolioSnapshot,
  SignalImpactResponse,
  MetaMetricsResponse,
  RiskSignal,
  MetaPayload,
} from '../types';

const API_BASE = '';

export async function fetchPortfolioWeights(
  ticker?: string,
  startDate?: string,
  endDate?: string
): Promise<{ data: PortfolioWeight[]; meta: MetaPayload }> {
  const params = new URLSearchParams();
  if (ticker) params.append('ticker', ticker);
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);

  const query = params.toString() ? `?${params.toString()}` : '';
  const res = await fetch(`${API_BASE}/portfolio/weights${query}`);
  if (!res.ok) throw new Error(`Failed to load weights: ${res.statusText}`);
  return res.json();
}

export async function fetchPortfolioNav(
  startDate?: string,
  endDate?: string
): Promise<{ data: NavPoint[]; meta: MetaPayload }> {
  const params = new URLSearchParams();
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);

  const query = params.toString() ? `?${params.toString()}` : '';
  const res = await fetch(`${API_BASE}/portfolio/nav${query}`);
  if (!res.ok) throw new Error(`Failed to load NAV: ${res.statusText}`);
  return res.json();
}

export async function fetchPortfolioSnapshot(date: string): Promise<PortfolioSnapshot> {
  const res = await fetch(`${API_BASE}/portfolio/snapshot?date=${encodeURIComponent(date)}`);
  if (!res.ok) throw new Error(`Failed to load snapshot for ${date}: ${res.statusText}`);
  return res.json();
}

export async function fetchSignalImpact(textId: string): Promise<SignalImpactResponse> {
  const res = await fetch(`${API_BASE}/signals/${encodeURIComponent(textId)}/impact`);
  if (!res.ok) throw new Error(`Failed to load signal impact: ${res.statusText}`);
  return res.json();
}

export async function fetchMetaMetrics(): Promise<MetaMetricsResponse> {
  const res = await fetch(`${API_BASE}/meta/metrics`);
  if (!res.ok) throw new Error(`Failed to load metrics: ${res.statusText}`);
  return res.json();
}

export async function fetchLatestSignals(n: number = 20): Promise<RiskSignal[]> {
  const res = await fetch(`${API_BASE}/signals/latest?n=${n}`);
  if (!res.ok) throw new Error(`Failed to load latest signals: ${res.statusText}`);
  return res.json();
}

export async function fetchHighImpactDays(limit: number = 10): Promise<import('../types').HighImpactDay[]> {
  const res = await fetch(`${API_BASE}/portfolio/high-impact-days?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to load high impact days: ${res.statusText}`);
  return res.json();
}
