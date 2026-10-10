// API client for Flask backend
const BASE = 'http://127.0.0.1:5000/api';

export interface HealthResponse {
  status: string;
  model_loaded: boolean;
}

export interface ModelInfoResponse {
  model_type?: string;
  training_samples?: number;
  confidence_threshold?: number;
  metrics?: {
    hamming_loss?: number;
    exact_match_ratio?: number;
  };
  feature_names?: string[];
}

export interface PipelineResponse {
  success: boolean;
  source_code?: string;
  error?: string;
  errors?: Array<{ message: string; line?: number }>;
  phases?: {
    tokens?: Array<{ type: string; value: string; line: number }>;
    ast?: Record<string, unknown>;
    symbol_table?: Array<{
      name: string;
      type: string;
      category: string;
      value?: string;
      scope_level: number;
      enclosing_function?: string;
      line: number;
    }>;
    semantic_errors?: Array<{ message: string; line?: number }>;
    tac_before?: unknown[];
    tac_after?: unknown[];
    optimized_code?: string;
  };
  ml?: {
    features?: Record<string, number>;
    recommendations?: Array<{
      pass: string;
      confidence: number;
      recommended: boolean;
      applied: boolean;
      explanation: string;
      result_type: string;
    }>;
    model_info?: Record<string, unknown>;
  };
  stats?: {
    instructions_before: number;
    instructions_after: number;
    reduction_count: number;
    reduction_percent: number;
    passes_recommended: string[];
    passes_applied: string[];
    result_type: string;
  };
}

export async function getHealth(): Promise<HealthResponse> {
  try {
    const res = await fetch(`${BASE}/health`);
    return res.json();
  } catch {
    return { status: 'offline', model_loaded: false };
  }
}

export async function getModelInfo(): Promise<ModelInfoResponse | null> {
  try {
    const res = await fetch(`${BASE}/model`);
    return res.json();
  } catch {
    return null;
  }
}

export async function analyzeSource(sourceCode: string): Promise<PipelineResponse> {
  const res = await fetch(`${BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_code: sourceCode }),
  });
  return res.json();
}

export async function tokenizeSource(sourceCode: string): Promise<PipelineResponse> {
  const res = await fetch(`${BASE}/tokenize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_code: sourceCode }),
  });
  return res.json();
}
