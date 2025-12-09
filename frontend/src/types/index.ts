export interface CustomerInput {
  name: string;
  email: string;
  insurance_needs: string;
  documents?: Record<string, string>;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
}

export interface SessionUpdate {
  additional_data?: Record<string, any>;
  chat_message?: string;
}

export interface WorkflowStep {
  id: string;
  name: string;
  description: string;
}

export interface SessionData {
  session_id: string;
  customer: CustomerInput;
  current_step: string;
  status: 'in_progress' | 'complete' | 'error';
  chat_history: ChatMessage[];
  step_results?: Record<string, any>;
  agent_step?: string;
  agent_label?: string;
}

export interface StartSessionResponse {
  session_id: string;
  next_step: string;
  welcome_message: string;
  status: string;
  agent_step?: string;
  agent_label?: string;
}

export interface ChatResponse {
  response: string;
  session_status: string;
  current_step: string;
  agent_step?: string;
  agent_label?: string;
  decision?: any;
  user_message?: string;
  final?: boolean;
  passed?: boolean;
  advanced?: boolean;
  advancement?: { from: string; to: string | null } | null;
  thread_id?: string;
  run_id?: string;
}

export interface RunStepResponse {
  status: 'step_complete' | 'onboarding_complete' | 'awaiting_input' | 'error' |
  'step_passed' | 'step_failed' | 'workflow_complete' | 'awaiting_employee_input';
  next_step?: string;
  missing_fields?: string[];
  message?: string;
  result?: any;
  decision?: any;
  passed?: boolean;
  current_step?: string;
  conversation_continues?: boolean;
  current_step_result?: any;
  agent_step?: string;
  agent_label?: string;
}

export interface HealthResponse {
  status: string;
  timestamp: number;
  services: {
    api: string;
    azure_openai: string;
  };
  active_sessions: number;
}

// RAG Document Management Types
export interface RAGDocument {
  id: number; // representative document id (MIN(id) per filename)
  filename: string;
  category: string;
  chunk_count: number;
  uploaded_at: string | null;
  status: 'pending' | 'processing' | 'indexed' | 'error';
  error_message?: string;
}

export interface RAGDocumentDetails extends RAGDocument {
  total_chars: number;
  sample_chunks: Array<{
    index: number;
    preview: string;
  }>;
}

export interface DocumentChunk {
  index: number;
  content: string;
  category: string;
  char_count: number;
  uploaded_at: string | null;
}

export interface DocumentChunksResponse {
  id?: number;
  filename: string;
  chunk_count: number;
  chunks: DocumentChunk[];
}

export interface DocumentUploadResponse {
  status: string;
  filename: string;
  category: string;
  chunk_size: number;
  chunks_created: number;
}

export interface DocumentListResponse {
  documents: RAGDocument[];
}

export interface DocumentDeleteResponse {
  status: string;
  filename: string;
  chunks_deleted: number;
}

// Session Panel Types
export interface BlobDocument {
  name: string;
  size: number;
  created?: string | null;
  last_modified?: string | null;
  content_type?: string | null;
  metadata?: Record<string, any>;
}

export interface SessionPanelData {
  session: {
    session_id: string;
    customer: CustomerInput;
    current_step: string;
    status: string;
  };
  crm: any; // shape from Postgres MCP get_customer_by_email
  previous_sessions: {
    sessions?: Array<{
      id: string;
      status: string;
      current_step: string;
      created_at?: string | null;
      updated_at?: string | null;
    }>;
    error?: string;
  };
  documents: {
    document_count: number;
    documents: BlobDocument[];
    error?: string;
    folder?: string;
    account_id?: string;
  };
}