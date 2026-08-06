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

export interface SessionSummary {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  turn_count: number;
  last_preview: string;
}

export interface SessionTurnRaw {
  turn_id: number;
  user_query: string;
  agent_response: string;
  metadata?: Record<string, any>;
}

export interface SessionDetail {
  metadata: SessionSummary;
  turns: SessionTurnRaw[];
  last_response?: AnalysisResponse | null;
}

