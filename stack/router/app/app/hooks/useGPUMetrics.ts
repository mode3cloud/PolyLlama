import { useState, useEffect } from 'react'
import { getApiUrl } from '../utils'

interface GPUMetrics {
  index: number
  memory_used: number
  memory_total: number
  gpu_utilization: number
  temperature: number
  power_draw: number
  timestamp: number
}

interface CPUMetrics {
  memory_used: number
  memory_total: number
  temperature?: number
  is_cpu_instance: boolean
  timestamp: number
}

interface InstanceMetrics {
  instance: string
  type: 'gpu' | 'cpu'
  group_name?: string
  devices?: GPUMetrics[]
  cpu_metrics?: CPUMetrics
}

interface GPUMetricsResponse {
  metrics: InstanceMetrics[]
  timestamp: number
}

export function useGPUMetrics(instanceName?: string) {
  const [metrics, setMetrics] = useState<Record<string, InstanceMetrics>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await fetch(getApiUrl('/api/ui/gpu-metrics'))
        if (!response.ok) throw new Error('Failed to fetch metrics')
        
        const data: GPUMetricsResponse = await response.json()
        const metricsMap: Record<string, InstanceMetrics> = {}
        
        data.metrics.forEach((m: InstanceMetrics) => {
          metricsMap[m.instance] = m
        })
        
        setMetrics(metricsMap)
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
      } finally {
        setLoading(false)
      }
    }

    fetchMetrics()
    const interval = setInterval(fetchMetrics, 2000) // Update every 2 seconds
    
    return () => clearInterval(interval)
  }, [])

  if (instanceName) {
    return {
      metrics: metrics[instanceName],
      loading,
      error
    }
  }

  return { metrics, loading, error }
}