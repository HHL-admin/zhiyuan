export interface SourceDocument {
  content: string;
  metadata: {
    source: string;
    [key: string]: any;
  };
  score?: number;
}

export interface QueryResponse {
  answer: string;
  sources: SourceDocument[];
  question: string;
  timestamp: string;
}

export interface QueryRequest {
  question: string;
  top_k?: number;
  api_key?: string;  // 用户自己的 API Key
  api_base_url?: string;  // API 中转地址
  model?: string;  // AI 模型选择
  temperature?: number;  // 温度参数
}

export interface DocumentListItem {
  filename: string;
  size: number;
  upload_time: string;
  chunk_count?: number;
}

export interface DocumentListResponse {
  documents: DocumentListItem[];
  total: number;
}

export interface DocumentUploadResponse {
  filename: string;
  size: number;
  chunks: number;
  message: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  vectorstore_status: string;
}

export interface StatsResponse {
  document_count: number;
  chunk_count: number;
  vectorstore_status: string;
}
