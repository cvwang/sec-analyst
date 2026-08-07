import { useState, useEffect } from 'react';

export interface MetricsResponse {
  ticker: string;
  start_year: string;
  end_year: string;
  metrics: {
    start_period: {
      revenue: number;
      operating_income: number;
      net_income: number;
      operating_margin: number;
    };
    end_period: {
      revenue: number;
      operating_income: number;
      net_income: number;
      operating_margin: number;
    };
    variances: {
      revenue_yoy_change_percent: number;
      operating_income_yoy_change_percent: number;
      net_income_yoy_change_percent: number;
      operating_margin_yoy_change_bps: number;
    };
  };
}

export interface PeerMetricsResponse {
  ticker: string;
  peer_ticker: string;
  year: string;
  primary: {
    ticker: string;
    revenue: number;
    operating_income: number;
    net_income: number;
    operating_margin: number;
  };
  peer: {
    ticker: string;
    revenue: number;
    operating_income: number;
    net_income: number;
    operating_margin: number;
  };
}

// In-memory client cache for instant 0ms metric re-rendering across session switches
const metricsCache = new Map<string, MetricsResponse>();
const peerMetricsCache = new Map<string, PeerMetricsResponse>();

export function useFetchMetrics(ticker: any, startYear: any, endYear: any) {
  let safeTicker = '';
  if (typeof ticker === 'string') {
    safeTicker = ticker.trim().toUpperCase();
  } else if (Array.isArray(ticker) && ticker.length > 0) {
    safeTicker = String(ticker[0]).trim().toUpperCase();
  } else if (ticker) {
    safeTicker = String(ticker).trim().toUpperCase();
  }

  const safeStartYear = startYear ? String(startYear).trim() : '';
  const safeEndYear = endYear ? String(endYear).trim() : '';

  const cacheKey = safeTicker && safeStartYear && safeEndYear ? `${safeTicker}_${safeStartYear}_${safeEndYear}` : null;

  const [data, setData] = useState<MetricsResponse | null>(() => {
    return cacheKey ? metricsCache.get(cacheKey) || null : null;
  });
  const [isLoading, setIsLoading] = useState<boolean>(() => {
    return cacheKey ? !metricsCache.has(cacheKey) : false;
  });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!safeTicker || !safeStartYear || !safeEndYear || !cacheKey) {
      setIsLoading(false);
      return;
    }

    if (metricsCache.has(cacheKey)) {
      setData(metricsCache.get(cacheKey)!);
      setIsLoading(false);
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    fetch(`/api/v1/metrics?ticker=${encodeURIComponent(safeTicker)}&start_year=${encodeURIComponent(safeStartYear)}&end_year=${encodeURIComponent(safeEndYear)}`)
      .then((res) => {
        if (!res.ok) {
          throw new Error(`Failed to fetch metrics: ${res.statusText}`);
        }
        return res.json();
      })
      .then((json: MetricsResponse) => {
        metricsCache.set(cacheKey, json);
        if (isMounted) {
          setData(json);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Error fetching metrics');
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [safeTicker, safeStartYear, safeEndYear, cacheKey]);

  return { data, isLoading, error };
}

export function useFetchPeerMetrics(ticker: any, peerTicker: any, year: any) {
  let safeTicker = typeof ticker === 'string' ? ticker.trim().toUpperCase() : (Array.isArray(ticker) && ticker.length > 0 ? String(ticker[0]).trim().toUpperCase() : '');
  let safePeerTicker = typeof peerTicker === 'string' ? peerTicker.trim().toUpperCase() : (Array.isArray(peerTicker) && peerTicker.length > 0 ? String(peerTicker[0]).trim().toUpperCase() : '');
  const safeYear = year ? String(year).trim() : '2023';

  if (!safePeerTicker && safeTicker.includes(',')) {
    const parts = safeTicker.split(',').map((s) => s.trim().toUpperCase());
    safeTicker = parts[0];
    safePeerTicker = parts[1] || 'AAPL';
  }

  const cacheKey = safeTicker && safePeerTicker && safeYear ? `${safeTicker}_PEER_${safePeerTicker}_${safeYear}` : null;

  const [data, setData] = useState<PeerMetricsResponse | null>(() => {
    return cacheKey ? peerMetricsCache.get(cacheKey) || null : null;
  });
  const [isLoading, setIsLoading] = useState<boolean>(() => {
    return cacheKey ? !peerMetricsCache.has(cacheKey) : false;
  });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!safeTicker || !safePeerTicker || !safeYear || !cacheKey) {
      setIsLoading(false);
      return;
    }

    if (peerMetricsCache.has(cacheKey)) {
      setData(peerMetricsCache.get(cacheKey)!);
      setIsLoading(false);
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    fetch(`/api/v1/peer_metrics?ticker=${encodeURIComponent(safeTicker)}&peer_ticker=${encodeURIComponent(safePeerTicker)}&year=${encodeURIComponent(safeYear)}`)
      .then((res) => {
        if (!res.ok) {
          throw new Error(`Failed to fetch peer metrics: ${res.statusText}`);
        }
        return res.json();
      })
      .then((json: PeerMetricsResponse) => {
        peerMetricsCache.set(cacheKey, json);
        if (isMounted) {
          setData(json);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Error fetching peer metrics');
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [safeTicker, safePeerTicker, safeYear, cacheKey]);

  return { data, isLoading, error };
}
