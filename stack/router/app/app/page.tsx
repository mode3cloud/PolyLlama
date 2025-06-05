'use client'

import { useState, useEffect, useCallback } from 'react'
import Header from './components/Header'
import SystemOverview from './components/SystemOverview'
import InstanceGrid from './components/InstanceGrid'
import ModelManagement from './components/ModelManagement'
import LoadModelModal from './components/LoadModelModal'
import { Instance, Model, RunningModels, ModelMappings } from './types'
import styles from './page.module.css'

export default function Home() {
  // State
  const [instances, setInstances] = useState<Instance[]>([])
  const [instanceStatuses, setInstanceStatuses] = useState<Record<string, any>>({})
  const [availableModels, setAvailableModels] = useState<Model[]>([])
  const [runningModels, setRunningModels] = useState<RunningModels>({})
  const [modelMappings, setModelMappings] = useState<ModelMappings>({})
  const [modelContexts, setModelContexts] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(true)
  const [loadModalOpen, setLoadModalOpen] = useState(false)
  const [selectedModel, setSelectedModel] = useState<string>('')

  // Initialize instances
  const initializeInstances = useCallback(async () => {
    try {
      const response = await fetch('/api/ui/instance-count')
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
      const [statusRes, modelsRes, runningRes, mappingsRes, contextsRes] = await Promise.all([
        fetch('/api/ui/instance-status'),
        fetch('/api/tags'),
        fetch('/api/ui/running-models'),
        fetch('/api/ui/model-mappings'),
        fetch('/api/ui/get-contexts')
      ])

      if (statusRes.ok) {
        const data = await statusRes.json()
        const statuses: Record<string, any> = {}
        data.instances.forEach((instance: any) => {
          statuses[instance.name] = instance
        })
        setInstanceStatuses(statuses)
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
        const data = await mappingsRes.json()
        setModelMappings(data.mappings || {})
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
          const syncResponse = await fetch('/api/ui/sync-contexts')
          if (syncResponse.ok) {
            const syncData = await syncResponse.json()
            console.log(`Synced context sizes for ${syncData.synced_count} models`)
            // Re-fetch contexts after sync
            const contextsRes2 = await fetch('/api/ui/get-contexts')
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
    } catch (error) {
      console.error('Error refreshing data:', error)
      setLoading(false)
    }
  }, [])

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
        const response = await fetch('/api/generate', {
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

  // Initial data fetch
  useEffect(() => {
    if (instances.length > 0) {
      refreshData()
      // Auto-refresh every 5 seconds
      const interval = setInterval(refreshData, 5000)
      return () => clearInterval(interval)
    }
  }, [instances, refreshData])

  if (loading) {
    return (
      <div className={styles.container}>
        <Header onRefresh={refreshData} />
        <main className={styles.main}>
          <div className={styles.loading}>Loading...</div>
        </main>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <Header onRefresh={refreshData} />
      <main className={styles.main}>
        <SystemOverview 
          instances={instances}
          instanceStatuses={instanceStatuses}
          runningModels={runningModels}
        />
        
        <InstanceGrid
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
          onLoadModel={handleLoadModel}
          onUnloadModel={handleUnloadModel}
        />
      </main>

      <LoadModelModal
        isOpen={loadModalOpen}
        modelName={selectedModel}
        instances={instances}
        onClose={() => setLoadModalOpen(false)}
        onConfirm={async (modelName, instanceName, contextLength) => {
          // Handle model loading
          try {
            const payload: any = { model: modelName, prompt: "", stream: false }
            if (contextLength) {
              payload.options = { num_ctx: parseInt(contextLength) }
            }

            const response = await fetch('/api/generate', {
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
                  await fetch('/api/ui/store-context', {
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
  )
}