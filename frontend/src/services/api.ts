import axios from 'axios';
import type {
  CustomerInput,
  ChatMessage,
  SessionUpdate,
  WorkflowStep,
  SessionData,
  StartSessionResponse,
  ChatResponse,
  RunStepResponse,
  HealthResponse,
  DocumentUploadResponse,
  DocumentListResponse,
  DocumentDeleteResponse,
  RAGDocumentDetails,
  DocumentChunksResponse,
  SessionPanelData,
  BlobDocument
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for authentication (no longer needed since backend handles auth)
apiClient.interceptors.request.use(
  (config) => {
    // API key is now handled by the backend from environment variables
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Authentication errors are now handled by backend
      console.error('Authentication failed - check backend configuration');
    }
    return Promise.reject(error);
  }
);

export const apiService = {
  // Health check
  async healthCheck(): Promise<HealthResponse> {
    const response = await apiClient.get('/health');
    return response.data;
  },

  // Start a new KYC session
  async startSession(customer: CustomerInput): Promise<StartSessionResponse> {
    const response = await apiClient.post('/start-session', customer);
    return response.data;
  },

  // Get session details
  async getSession(sessionId: string): Promise<SessionData> {
    const response = await apiClient.get(`/session/${sessionId}`);
    return response.data;
  },

  // Send chat message
  async sendChatMessage(sessionId: string, message: ChatMessage): Promise<ChatResponse> {
    const response = await apiClient.post(`/chat/${sessionId}`, message);
    // Return enriched ChatResponse with agent metadata & decision info
    return response.data as ChatResponse;
  },

  // Deprecated: manual step progression (to be removed after UI refactor)
  async runStep(sessionId: string, stepData?: { step?: string; data?: Record<string, any> }): Promise<RunStepResponse> {
    const response = await apiClient.post(`/run-step/${sessionId}`, stepData || {});
    return response.data;
  },


  // Update session
  async updateSession(sessionId: string, update: SessionUpdate): Promise<{ status: string; session_id: string }> {
    const response = await apiClient.put(`/session/${sessionId}`, update);
    return response.data;
  },

  // Get workflow steps
  async getWorkflowSteps(): Promise<{ steps: WorkflowStep[] }> {
    const response = await apiClient.get('/steps');
    return response.data;
  },

  // End session
  async endSession(sessionId: string): Promise<{ status: string; session_id: string }> {
    const response = await apiClient.delete(`/session/${sessionId}`);
    return response.data;
  },

  // =====================
  // Session Panel & Documents
  // =====================

  async getSessionPanelData(sessionId: string, documentType?: string): Promise<SessionPanelData> {
    const response = await apiClient.get(`/session/${sessionId}/panel-data`, {
      params: documentType ? { document_type: documentType } : undefined,
    });
    return response.data;
  },

  async listSessionDocuments(sessionId: string, documentType?: string): Promise<{ document_count: number; documents: BlobDocument[] }> {
    const response = await apiClient.get(`/session/${sessionId}/documents`, {
      params: documentType ? { document_type: documentType } : undefined,
    });
    return response.data;
  },

  async uploadSessionDocument(sessionId: string, file: File, documentType: string = 'other'): Promise<{ status: string; uploaded: boolean; blob_path: string; size: number }> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post(`/session/${sessionId}/documents/upload`, formData, {
      params: { document_type: documentType },
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  // =====================
  // RAG Document Management
  // =====================

  // Upload document
  async uploadDocument(file: File, category: string, chunkSize: number = 1000): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    // category and chunk_size are query params in the endpoint definition if not in body
    // checking main.py: category and chunk_size are query params

    const response = await apiClient.post('/policies/upload-file', formData, {
      params: { category, chunk_size: chunkSize },
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // List all documents
  async listDocuments(): Promise<DocumentListResponse> {
    const response = await apiClient.get('/policies/documents');
    return response.data;
  },

  // Get document details
  async getDocument(filename: string): Promise<RAGDocumentDetails> {
    const response = await apiClient.get(`/policies/documents/by-filename/${encodeURIComponent(filename)}`);
    return response.data;
  },

  // Get document chunks
  async getDocumentChunksById(documentId: number): Promise<DocumentChunksResponse> {
    const response = await apiClient.get(`/policies/documents/${documentId}/chunks`);
    return response.data;
  },

  // Delete document
  async deleteDocument(filename: string): Promise<DocumentDeleteResponse> {
    const response = await apiClient.delete(`/policies/documents/by-filename/${encodeURIComponent(filename)}`);
    return response.data;
  },
};

export default apiService;