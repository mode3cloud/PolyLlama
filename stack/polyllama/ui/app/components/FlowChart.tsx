'use client'

import { useState, useEffect, useCallback } from 'react'
import { Instance, RunningModels } from '../types'
import PolyLlamaInstance from './PolyLlamaInstance'
import { GPUDeviceInfo } from './GPUDevice'
import { useGPUMetrics } from '../hooks/useGPUMetrics'
import { getApiUrl } from '../utils'

interface FlowChartProps {
  instances: Instance[];
  instanceStatuses: Record<string, any>;
  runningModels: RunningModels;
  modelContexts: Record<string, number>;
  onRefresh: () => void;
}

interface GPUGroup {
  name: string;
  indices: number[];
  devices: GPUDeviceInfo[];
}

interface GPUConfig {
  groups: GPUGroup[];
  instance_mapping: Record<string, number>;
}

export default function FlowChart({ instances, instanceStatuses, runningModels, modelContexts, onRefresh }: FlowChartProps) {
  const [gpuConfig, setGpuConfig] = useState<GPUConfig | null>(null)
  const { metrics } = useGPUMetrics() as { metrics: Record<string, any>; loading: boolean; error: string | null }

  useEffect(() => {
    // Fetch GPU configuration from backend
    fetch(getApiUrl('/api/ui/gpu-config'))
      .then(res => res.json())
      .then(data => setGpuConfig(data))
      .catch(err => console.error('Failed to fetch GPU config:', err))
  }, [])

  const handleUnloadModel = useCallback(async (modelName: string, instanceName: string) => {
    if (!confirm(`Are you sure you want to unload ${modelName} from ${instanceName}?`)) {
      return
    }

    try {
      const response = await fetch(getApiUrl('/api/generate'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Target-Instance': instanceName
        },
        body: JSON.stringify({
          model: modelName,
          keep_alive: 0
        })
      })

      if (!response.ok) {
        throw new Error(`Failed to unload from ${instanceName}: ${response.statusText}`)
      }

      setTimeout(onRefresh, 2000)
    } catch (error) {
      console.error('Error unloading model:', error)
    }
  }, [onRefresh])

  // Helper function to get GPU group info for an instance
  const getGPUGroupInfo = (instanceName: string) => {
    if (!gpuConfig) {
      return { groupName: 'CPU-only', devices: [] }
    }

    const groupIndex = gpuConfig.instance_mapping[instanceName]

    if (groupIndex === undefined || groupIndex === -1 || !gpuConfig.groups[groupIndex]) {
      return { groupName: 'CPU-only', devices: [] }
    }

    const group = gpuConfig.groups[groupIndex]

    // Create a deep copy of devices to avoid reference issues
    return {
      groupName: group.name,
      devices: group.devices.map(device => ({ ...device }))
    }
  }

  return (
    <div className="w-full">
      <div>
        <div className="space-y-6">
          {instances.map(instance => {
            const status = instanceStatuses[instance.name] || { status: 'offline', name: instance.name }
            const { groupName, devices } = getGPUGroupInfo(instance.name)
            
            // Get metrics for this instance
            const instanceMetrics = metrics[instance.name]
            const cpuMetrics = instanceMetrics?.type === 'cpu' ? instanceMetrics.cpu_metrics : undefined
            const gpuMetrics = instanceMetrics?.type === 'gpu' ? instanceMetrics.devices : undefined

            return (
              <PolyLlamaInstance
                key={instance.name}
                instance={instance}
                status={status}
                runningModels={runningModels}
                modelContexts={modelContexts}
                gpuGroupName={groupName !== 'CPU-only' ? groupName : undefined}
                gpuDevices={devices}
                gpuMetrics={gpuMetrics}
                cpuMetrics={cpuMetrics}
                onUnloadModel={handleUnloadModel}
              />
            )
          })}
        </div>
      </div>
    </div>
  )
}