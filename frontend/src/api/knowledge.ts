import { apiClient } from './client';
import type {
  QueryRequest,
  QueryResponse,
  DocumentListResponse,
  DocumentUploadResponse,
  HealthResponse,
  StatsResponse,
} from '../types';

export const knowledgeApi = {
  // 健康检查
  healthCheck: async (): Promise<HealthResponse> => {
    const response = await apiClient.get('/health');
    return response.data;
  },

  // 获取统计信息
  getStats: async (): Promise<StatsResponse> => {
    const response = await apiClient.get('/stats');
    return response.data;
  },

  // 上传文档
  uploadDocument: async (file: File): Promise<DocumentUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // 获取文档列表
  getDocuments: async (): Promise<DocumentListResponse> => {
    const response = await apiClient.get('/documents');
    return response.data;
  },

  // 删除文档
  deleteDocument: async (filename: string): Promise<{ message: string }> => {
    const response = await apiClient.delete(`/documents/${filename}`);
    return response.data;
  },

  // 查询（非流式）
  query: async (request: QueryRequest): Promise<QueryResponse> => {
    const response = await apiClient.post('/query', request);
    return response.data;
  },

  // 查询（流式）
  queryStream: async (
    request: QueryRequest,
    onMessage: (data: { type: string; data: any }) => void,
    onError?: (error: Error) => void,
    onComplete?: () => void
  ) => {
    const token = localStorage.getItem('token');

    console.log('[QueryStream] 开始请求:', request);

    let timeoutId: number | null = null;
    let isStreamActive = true;

    // 60秒超时保护
    timeoutId = setTimeout(() => {
      if (isStreamActive) {
        console.error('[QueryStream] 请求超时(60秒)');
        isStreamActive = false;
        onError?.(new Error('查询超时,请检查网络连接或稍后重试'));
      }
    }, 60000);

    try {
      const response = await fetch(`${apiClient.defaults.baseURL}/query/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : '',
        },
        body: JSON.stringify(request),
      });

      console.log('[QueryStream] 响应状态:', response.status);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('[QueryStream] HTTP错误:', response.status, errorText);
        isStreamActive = false;
        if (timeoutId) clearTimeout(timeoutId);
        throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('Response body is null');
      }
      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          console.log('[QueryStream] 流式响应结束(done)');
          isStreamActive = false;
          if (timeoutId) clearTimeout(timeoutId);
          onComplete?.();
          break;
        }

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);

            if (data === '[DONE]') {
              console.log('[QueryStream] 流式响应结束([DONE])');
              isStreamActive = false;
              if (timeoutId) clearTimeout(timeoutId);
              onComplete?.();
              break;
            }

            try {
              const parsed = JSON.parse(data);
              onMessage(parsed);
            } catch (e) {
              console.error('[QueryStream] 解析SSE数据失败:', e, 'raw:', data);
            }
          }
        }
      }
    } catch (error) {
      console.error('[QueryStream] 流式读取异常:', error);
      isStreamActive = false;
      if (timeoutId) clearTimeout(timeoutId);
      onError?.(error as Error);
    }
  },
};
