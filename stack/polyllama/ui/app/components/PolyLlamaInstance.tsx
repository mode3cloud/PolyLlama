'use client'

import { Instance, RunningModels } from '../types'
import GPUDevice, { GPUDeviceInfo } from './GPUDevice'
import CPUMetrics from './CPUMetrics'

interface CPUMetricsData {
  memory_used: number
  memory_total: number
  temperature?: number
  is_cpu_instance: boolean
  timestamp: number
}

interface GPUMetrics {
  index: number
  memory_used: number
  memory_total: number
  gpu_utilization: number
  temperature: number
  power_draw: number
  timestamp: number
}

interface PolyLlamaInstanceProps {
  instance: Instance;
  status: any;
  runningModels: RunningModels;
  modelContexts: Record<string, number>;
  gpuGroupName?: string;
  gpuDevices?: GPUDeviceInfo[];
  gpuMetrics?: GPUMetrics[];
  cpuMetrics?: CPUMetricsData;
  onUnloadModel: (modelName: string, instanceName: string) => void;
}

export default function PolyLlamaInstance({
  instance,
  status,
  runningModels,
  modelContexts,
  gpuGroupName,
  gpuDevices,
  gpuMetrics,
  cpuMetrics,
  onUnloadModel
}: PolyLlamaInstanceProps) {
  const instanceModels = Object.keys(runningModels).filter(model =>
    runningModels[model].includes(instance.name)
  )
  const isOnline = status.status === 'online'

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Column 1: Instance details */}
      <div className="bg-white rounded-xl overflow-hidden shadow-sm transition-all hover:shadow-md">
        {/* Header - show CPU badge for CPU instances */}
        <div className="bg-gradient-to-r from-gray-700 to-gray-800 text-white px-6 py-5 flex items-center justify-between">
          <div className="flex items-center gap-2 text-lg font-semibold">
            <span className={`w-2.5 h-2.5 rounded-full ${isOnline ? 'bg-success animate-pulse-soft' : 'bg-danger'}`}></span>
            <span>{instance.name}</span>
          </div>
          <span className="text-xs bg-white/20 px-3 py-1 rounded">
            {gpuGroupName || 'CPU'}
          </span>
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Status and Models Count */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="bg-gray-50 p-3 rounded-md">
              <div className="text-xs text-gray-600 mb-1">Status</div>
              <div className="text-lg font-semibold text-gray-900">{isOnline ? 'Online' : 'Offline'}</div>
            </div>
            <div className="bg-gray-50 p-3 rounded-md">
              <div className="text-xs text-gray-600 mb-1">Models</div>
              <div className="text-lg font-semibold text-gray-900">{instanceModels.length}</div>
            </div>
          </div>

          {/* Loaded Models */}
          <div className="mt-4">
            <div className="text-sm text-gray-600 mb-2 font-medium">Loaded Models</div>
            {instanceModels.length > 0 ? (
              instanceModels.map(model => {
                const contextInfo = modelContexts[model] ? ` (ctx: ${modelContexts[model]})` : ''
                return (
                  <div key={model} className="inline-flex items-center gap-1 mr-2 mb-2">
                    <span className="inline-block bg-success text-white px-3 py-1.5 rounded-md text-xs font-medium">
                      {model}
                      <small className="text-white/80 ml-1">{contextInfo}</small>
                    </span>
                    <button
                      className="bg-danger text-white rounded-full w-[18px] h-[18px] text-xs leading-none cursor-pointer flex items-center justify-center transition-all opacity-80 hover:opacity-100 hover:scale-110"
                      onClick={() => onUnloadModel(model, instance.name)}
                      title={`Unload ${model} from ${instance.name}`}
                    >
                      ×
                    </button>
                  </div>
                )
              })
            ) : (
              <div className="text-sm text-gray-500">No models loaded</div>
            )}
          </div>
        </div>
      </div>

      {/* Column 2: GPU Devices OR CPU Metrics */}
      {gpuDevices && gpuDevices.length > 0 ? (
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <div className="text-sm text-gray-600 mb-3 font-medium">GPU Devices</div>
          <div className="space-y-2">
            {gpuDevices.map((device) => {
              const deviceMetrics = gpuMetrics?.find(m => m.index === device.index)
              return (
                <GPUDevice
                  key={device.index}
                  device={device}
                  deviceMetrics={deviceMetrics}
                />
              )
            })}
          </div>
        </div>
      ) : cpuMetrics ? (
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <div className="text-sm text-gray-600 mb-3 font-medium">System Resources</div>
          <CPUMetrics metrics={cpuMetrics} />
        </div>
      ) : null}
    </div>
  )
}