'use client'

import { useCallback } from 'react'
import { Instance, RunningModels } from '../types'

interface InstanceGridProps {
  instances: Instance[];
  instanceStatuses: Record<string, any>;
  runningModels: RunningModels;
  modelContexts: Record<string, number>;
  onRefresh: () => void;
}

export default function InstanceGrid({ 
  instances, 
  instanceStatuses, 
  runningModels, 
  modelContexts,
  onRefresh 
}: InstanceGridProps) {
  
  const handleUnloadModel = useCallback(async (modelName: string, instanceName: string) => {
    if (!confirm(`Are you sure you want to unload ${modelName} from ${instanceName}?`)) {
      return
    }

    try {
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
        throw new Error(`Failed to unload from ${instanceName}: ${response.statusText}`)
      }

      setTimeout(onRefresh, 2000)
      // TODO: Add success toast
    } catch (error) {
      console.error('Error unloading model:', error)
      // TODO: Add error toast
    }
  }, [onRefresh])

  return (
    <section className="mb-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-semibold text-gray-900">Instance Management</h2>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {instances.map(instance => {
          const status = instanceStatuses[instance.name] || { status: 'offline', name: instance.name }
          const instanceModels = Object.keys(runningModels).filter(model =>
            runningModels[model].includes(instance.name)
          )
          const isOnline = status.status === 'online'
          const instanceNumber = instance.name.replace('polyllama', '')

          return (
            <div key={instance.name} className="bg-white rounded-xl overflow-hidden shadow-sm transition-all hover:shadow-md">
              <div className="bg-gradient-to-r from-gray-700 to-gray-800 text-white px-6 py-5 flex items-center justify-between">
                <div className="flex items-center gap-2 text-lg font-semibold">
                  <span className={`w-2.5 h-2.5 rounded-full ${isOnline ? 'bg-success animate-pulse-soft' : 'bg-danger'}`}></span>
                  <span>{instance.name}</span>
                </div>
                <span className="text-xs bg-white/20 px-3 py-1 rounded">GPU Group</span>
              </div>
              <div className="p-6">
                <div className="flex items-center gap-4 mb-6 pb-4 border-b border-gray-200">
                  <div className="bg-gray-100 px-4 py-2 rounded-md text-sm text-gray-700 font-medium">
                    GPU Group {instanceNumber}
                  </div>
                </div>
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
                            onClick={() => handleUnloadModel(model, instance.name)}
                            title={`Unload ${model} from ${instance.name}`}
                          >
                            ×
                          </button>
                        </div>
                      )
                    })
                  ) : (
                    <span className="inline-block bg-gray-100 text-gray-700 px-3 py-1.5 rounded-md text-xs font-medium">
                      No models loaded
                    </span>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}