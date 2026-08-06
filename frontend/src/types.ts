export interface TextChunk {
  content: string;
  highlight_excerpt?: string;
  company_name: string;
  fiscal_year: number;
  section: string;
  citation: string;
  gcs_uri?: string;
}

export interface HybridSearchResult {
  text_chunks?: TextChunk[];
  grounded_citations?: string[];
  query_type?: string;
}

export interface AnalysisResponse {
  is_success: boolean;
  ticker?: string;
  tickers?: string[];
  requested_years?: number[];
  query_type?: string;
  metric_name?: string;
  narrative?: string;
  model_used?: string;
  citations?: string[];
  hybrid_search_result?: HybridSearchResult;
  error?: string;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  timestamp: string;
  data?: AnalysisResponse;
}
