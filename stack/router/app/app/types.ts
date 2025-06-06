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