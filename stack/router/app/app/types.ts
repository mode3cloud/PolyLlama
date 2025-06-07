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
}

export interface ChatModel {
  id: string;
  name: string;
  provider: string;
  size?: number;
}

export interface ChatSession {
  id: string;
  created_at: string;
  message_count: number;
}

export interface StreamChunk {
  type: 'connected' | 'content' | 'complete' | 'error' | 'done';
  content?: string;
  error?: string;
}