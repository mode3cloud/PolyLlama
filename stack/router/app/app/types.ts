export interface Instance {
  name: string;
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

export interface InstanceStatus {
  name: string;
  status: 'online' | 'offline';
}