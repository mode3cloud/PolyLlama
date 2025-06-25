export interface Instance {
  name: string;
}

export interface InstanceStatus {
  name: string;
  status: 'online' | 'offline';
  version?: string;
  cuda_version?: string;
  gpu_count?: number;
}

export interface GPUConfig {
  groups: Array<{
    name: string;
    indices: number[];
    devices: Array<{
      index: number;
      name: string;
      pci_bus: string;
    }>;
  }>;
  instance_mapping: Record<string, number>; // Instance name to group index (-1 for CPU)
}

export interface Model {
  name: string;
  size: number;
  digest: string;
  modified_at: string;
  details?: {
    format?: string;
    family?: string;
    parameter_size?: string;
    quantization_level?: string;
  };
}

export interface RunningModels {
  [modelName: string]: string[]; // Array of instance names
}

export interface ModelMappings {
  [modelName: string]: string; // Maps model to instance
}

// Chat interface types
export interface ChatMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string;
  timestamp?: string;
  tool_name?: string;
  tool_call_id?: string;
  images?: ChatImage[];
}

export interface ChatImage {
  url: string;  // Base64 data URL or regular URL
  name?: string;
  type?: string;  // MIME type
}

export interface ChatModel {
  id: string;
  name: string;
  provider: string;
  size?: number;
  supports_vision?: boolean;
  supports_tools?: boolean;
}

export interface ChatSession {
  id: string;
  created_at: string;
  message_count: number;
}

export interface StreamChunk {
  type: 'connected' | 'content' | 'complete' | 'error' | 'done' | 'tool_result' | 'tool_error' | 'tool_call' | 'tool_call_streaming';
  content?: string;
  error?: string;
  // Tool-related fields
  name?: string;  // Tool name
  result?: string;  // Tool result
  tool_call?: {  // Tool call details
    id: string;
    name: string;
    arguments?: any;
    status?: 'started' | 'completed';
  };
}

export interface SearchModelTag {
  name: string;
  size: string;
}

export interface SearchModel {
  name: string;
  title: string;
  url: string;
  description: string;
  downloads: string | number;
  tags: SearchModelTag[];
  size: string;
  available_tags?: SearchModelTag[];
  missing_tags?: SearchModelTag[];
  is_locally_available?: boolean;
}

export interface SearchModelsResponse {
  models: SearchModel[];
  query: string;
  page: number;
  success: boolean;
  timestamp: number;
  error?: string;
}

export interface PullStatus {
  id: string;
  model: string;
  instance: string;
  status: 'starting' | 'in_progress' | 'completed' | 'failed' | 'timeout';
  progress: number;
  started_at: number;
  completed_at?: number;
  stage: string;
  error?: string;
  completed?: number; // bytes downloaded
  total?: number; // total bytes to download
}

export interface PullResponse {
  success: boolean;
  pull_id?: string;
  model?: string;
  instance?: string;
  message?: string;
  error?: string;
  existing_loader?: string;
}

export interface PullStatusResponse {
  success: boolean;
  pull_status?: PullStatus;
  error?: string;
}

export interface PullStatusesResponse {
  success: boolean;
  pull_statuses: PullStatus[];
  count: number;
}