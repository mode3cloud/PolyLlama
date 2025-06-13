'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import Header from './components/Header'
import SystemOverview from './components/SystemOverview'
import ModelManagement from './components/ModelManagement'
import LoadModelModal from './components/LoadModelModal'
import AuthWrapper from './components/AuthWrapper'
import { Instance, Model, RunningModels, InstanceStatus, GPUConfig } from './types'
import { fetchWithAuth } from './lib/fetchWithAuth'

// Backoff configuration
const INITIAL_INTERVAL = 5000 // 5 seconds
const MAX_INTERVAL = 30 * 60 * 1000 // 30 minutes
const BACKOFF_MULTIPLIER = 2

export default function Home() {
  // State
  const [instances, setInstances] = useState<Instance[]>([])
  const [instanceStatuses, setInstanceStatuses] = useState<Record<string, InstanceStatus>>({})
  const [gpuConfig, setGpuConfig] = useState<GPUConfig | null>(null)
  const [availableModels, setAvailableModels] = useState<Model[]>([])
  const [runningModels, setRunningModels] = useState<RunningModels>({})
  const [modelContexts, setModelContexts] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(true)
  const [loadModalOpen, setLoadModalOpen] = useState(false)
  const [selectedModel, setSelectedModel] = useState<string>('')
  
  // Backoff state
  const [backoffInterval, setBackoffInterval] = useState(INITIAL_INTERVAL)
  const [lastFetchFailed, setLastFetchFailed] = useState(false)
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  // Initialize instances
  const initializeInstances = useCallback(async () => {
    try {
      const response = await fetchWithAuth('/ui/api/instance-count')
      if (response.ok) {
        const data = await response.json()
        const instanceCount = data.instance_count || 2

        const newInstances: Instance[] = []
        for (let i = 1; i <= instanceCount; i++) {
          newInstances.push({ name: `polyllama${i}` })
        }
        setInstances(newInstances)
      }
    } catch (error) {
      console.error('Error initializing instances:', error)
    }
  }, [])

  // Fetch all data
  const refreshData = useCallback(async () => {
    try {
      // Only fetch GPU metrics, instance status, and GPU config for backoff
      const criticalPromises = [
        fetchWithAuth('/ui/api/instance-status'),
        fetchWithAuth('/ui/api/gpu-config'),
        fetchWithAuth('/ui/api/gpu-metrics')
      ]
      
      // Always fetch these regardless of critical API status
      const nonCriticalPromises = [
        fetchWithAuth('/ui/api/ollama-models'),
        fetchWithAuth('/ui/api/running-models'),
        fetchWithAuth('/ui/api/model-mappings'),
        fetchWithAuth('/ui/api/get-contexts')
      ]

      const [statusRes, gpuConfigRes, gpuMetricsRes] = await Promise.all(criticalPromises)
      const [modelsRes, runningRes, mappingsRes, contextsRes] = await Promise.all(nonCriticalPromises)

      // Check if any critical endpoints failed
      const criticalFailed = !statusRes.ok || !gpuConfigRes.ok || !gpuMetricsRes.ok

      if (statusRes.ok) {
        const data = await statusRes.json()
        const statuses: Record<string, InstanceStatus> = {}
        data.instances.forEach((instance: InstanceStatus) => {
          statuses[instance.name] = instance
        })
        setInstanceStatuses(statuses)
      }

      if (gpuConfigRes.ok) {
        const data = await gpuConfigRes.json()
        setGpuConfig(data)
      }

      if (modelsRes.ok) {
        const data = await modelsRes.json()
        const models = data.models || []
        models.sort((a: Model, b: Model) => a.name.localeCompare(b.name))
        setAvailableModels(models)
      }

      let runningModelsData: RunningModels = {}
      if (runningRes.ok) {
        const data = await runningRes.json()
        runningModelsData = data.running_models || {}
        setRunningModels(runningModelsData)
      }

      if (mappingsRes.ok) {
        await mappingsRes.json()
      }

      let currentContexts: Record<string, number> = {}
      if (contextsRes.ok) {
        const data = await contextsRes.json()
        currentContexts = data.contexts || {}
        setModelContexts(currentContexts)
      }

      // Sync contexts if needed
      const runningModelNames = Object.keys(runningModelsData)
      const hasRunningModels = runningModelNames.length > 0
      const hasMissingContexts = runningModelNames.some(model => !currentContexts[model])

      if (hasRunningModels && hasMissingContexts) {
        try {
          const syncResponse = await fetchWithAuth('/ui/api/sync-contexts')
          if (syncResponse.ok) {
            const syncData = await syncResponse.json()
            console.log(`Synced context sizes for ${syncData.synced_count} models`)
            // Re-fetch contexts after sync
            const contextsRes2 = await fetchWithAuth('/ui/api/get-contexts')
            if (contextsRes2.ok) {
              const data = await contextsRes2.json()
              setModelContexts(data.contexts || {})
            }
          }
        } catch (error) {
          console.error('Error syncing contexts:', error)
        }
      }

      setLoading(false)
      
      // Update backoff state based on critical endpoints
      if (criticalFailed && !lastFetchFailed) {
        // First failure - start backoff
        setLastFetchFailed(true)
        setBackoffInterval(prev => Math.min(prev * BACKOFF_MULTIPLIER, MAX_INTERVAL))
      } else if (!criticalFailed && lastFetchFailed) {
        // Recovery - reset backoff
        setLastFetchFailed(false)
        setBackoffInterval(INITIAL_INTERVAL)
      } else if (criticalFailed && lastFetchFailed) {
        // Continued failure - increase backoff
        setBackoffInterval(prev => Math.min(prev * BACKOFF_MULTIPLIER, MAX_INTERVAL))
      }
    } catch (error) {
      console.error('Error refreshing data:', error)
      setLoading(false)
      
      // Network error - apply backoff
      if (!lastFetchFailed) {
        setLastFetchFailed(true)
        setBackoffInterval(prev => Math.min(prev * BACKOFF_MULTIPLIER, MAX_INTERVAL))
      } else {
        setBackoffInterval(prev => Math.min(prev * BACKOFF_MULTIPLIER, MAX_INTERVAL))
      }
    }
  }, [lastFetchFailed])

  // Load model handler
  const handleLoadModel = useCallback((modelName: string) => {
    setSelectedModel(modelName)
    setLoadModalOpen(true)
  }, [])

  // Unload model handler
  const handleUnloadModel = useCallback(async (modelName: string) => {
    if (!confirm(`Are you sure you want to unload ${modelName}?`)) {
      return
    }

    try {
      const instances = runningModels[modelName] || []

      for (const instanceName of instances) {
        const response = await fetchWithAuth('/ui/api/generate', {
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
          throw new Error(`Failed to unload from ${instanceName}`)
        }
      }

      setTimeout(refreshData, 2000)
      // TODO: Add toast notification
    } catch (error) {
      console.error('Error unloading model:', error)
      // TODO: Add error toast
    }
  }, [runningModels, refreshData])

  // Initialize on mount
  useEffect(() => {
    initializeInstances()
  }, [initializeInstances])

  // Initial data fetch with backoff
  useEffect(() => {
    if (instances.length > 0) {
      refreshData()
    }
  }, [instances, refreshData])

  // Setup interval with backoff
  useEffect(() => {
    if (instances.length > 0) {
      // Clear existing interval
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }

      // Set new interval with current backoff duration
      intervalRef.current = setInterval(refreshData, backoffInterval)
      
      console.log(`Refresh interval set to ${backoffInterval / 1000} seconds`)

      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
        }
      }
    }
  }, [instances, backoffInterval, refreshData])

  return (
    <AuthWrapper>
      {loading ? (
        <div className="min-h-screen flex flex-col">
          <div className="fixed top-0 left-0 right-0 z-50">
            <Header onRefresh={refreshData} />
          </div>
          <main className="flex-1 max-w-[1400px] mx-auto p-4 md:p-8 w-full pt-20">
            <div className="text-center p-8 text-gray-500">Loading...</div>
          </main>
        </div>
      ) : (
        <div className="min-h-screen flex flex-col">
        <div className="fixed top-0 left-0 right-0 z-50">
          <Header onRefresh={refreshData} />
        </div>
        <main className="flex-1 max-w-[1400px] mx-auto p-4 md:p-8 w-full mt-12">
          <SystemOverview
            instances={instances}
            instanceStatuses={instanceStatuses}
            runningModels={runningModels}
            modelContexts={modelContexts}
            onRefresh={refreshData}
          />

          <ModelManagement
            availableModels={availableModels}
            runningModels={runningModels}
            modelContexts={modelContexts}
            instances={instances}
            instanceStatuses={instanceStatuses}
            onLoadModel={handleLoadModel}
            onUnloadModel={handleUnloadModel}
            onRefresh={refreshData}
          />
        </main>

        <LoadModelModal
          isOpen={loadModalOpen}
          modelName={selectedModel}
          instances={instances}
          instanceStatuses={instanceStatuses}
          gpuConfig={gpuConfig}
          runningModels={runningModels}
          onClose={() => setLoadModalOpen(false)}
          onConfirm={async (modelName, instanceName, contextLength) => {
            // Handle model loading
            try {
              const payload: any = { model: modelName, prompt: "", stream: false }
              if (contextLength) {
                payload.options = { num_ctx: parseInt(contextLength) }
              }

              const response = await fetchWithAuth('/ui/api/generate', {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                  'X-Target-Instance': instanceName
                },
                body: JSON.stringify(payload)
              })

              if (response.ok) {
                // Store context if specified
                if (contextLength) {
                  try {
                    await fetchWithAuth('/ui/api/store-context', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({
                        model: modelName,
                        num_ctx: parseInt(contextLength)
                      })
                    })
                  } catch (error) {
                    console.error('Failed to store context length:', error)
                  }
                }

                setLoadModalOpen(false)
                setTimeout(refreshData, 2000)
                // TODO: Add success toast
              } else {
                throw new Error(`Failed to load model: ${response.statusText}`)
              }
            } catch (error) {
              console.error('Error loading model:', error)
              // TODO: Add error toast
            }
          }}
        />
      </div>
      )}
    </AuthWrapper>
  )
}