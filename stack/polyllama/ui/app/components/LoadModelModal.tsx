'use client'

import { useState, useEffect } from 'react'
import { Instance, InstanceStatus, GPUConfig, RunningModels } from '../types'
import InstanceLoadButton from './InstanceLoadButton'

interface LoadModelModalProps {
  isOpen: boolean;
  modelName: string;
  instances: Instance[];
  instanceStatuses: Record<string, InstanceStatus>;
  gpuConfig: GPUConfig | null;
  runningModels: RunningModels;
  onClose: () => void;
  onConfirm: (modelName: string, instanceName: string, contextLength?: string) => Promise<void>;
}

export default function LoadModelModal({
  isOpen,
  modelName,
  instances,
  instanceStatuses,
  gpuConfig,
  runningModels,
  onClose,
  onConfirm
}: LoadModelModalProps) {
  const formatNumber = (num: number): string => {
    if (num >= 1000000) {
      return `${(num / 1000000).toFixed(1)}M`
    } else if (num >= 1000) {
      return `${(num / 1000).toFixed(1)}K`
    }
    return num.toString()
  }
  const [contextLength, setContextLength] = useState('')
  const [contextPercentage, setContextPercentage] = useState('100')
  const [defaultContext, setDefaultContext] = useState<number | null>(null)
  const [loadingInstances, setLoadingInstances] = useState<Set<string>>(new Set())
  const [loadingErrors, setLoadingErrors] = useState<Record<string, string>>({})

  const fetchModelDetails = async () => {
    try {
      const response = await fetch('/ui/api/model-details', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelName })
      })

      if (response.ok) {
        const data = await response.json()

        // Extract default context size from model info
        if (data.model_info && data.details && data.details.family) {
          const contextKey = data.details.family + '.context_length'
          const contextValue = data.model_info[contextKey]
          if (contextValue) {
            setDefaultContext(contextValue)
          }
        }
      }
    } catch (error) {
      console.error('Error fetching model details:', error)
    }
  }

  useEffect(() => {
    if (isOpen && modelName) {
      // Fetch model details to get default context
      fetchModelDetails()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, modelName])

  const handleInstanceLoad = async (instanceName: string) => {
    setLoadingInstances(prev => new Set([...prev, instanceName]))
    setLoadingErrors(prev => {
      const newErrors = { ...prev }
      delete newErrors[instanceName]
      return newErrors
    })

    try {
      // Calculate actual context length based on percentage
      const actualContextLength = defaultContext && contextPercentage !== '100' 
        ? Math.floor((defaultContext * parseInt(contextPercentage)) / 100).toString()
        : contextLength

      await onConfirm(modelName, instanceName, actualContextLength)
    } catch (error) {
      setLoadingErrors(prev => ({
        ...prev,
        [instanceName]: error instanceof Error ? error.message : 'Loading failed'
      }))
    } finally {
      setLoadingInstances(prev => {
        const newSet = new Set(prev)
        newSet.delete(instanceName)
        return newSet
      })
    }
  }

  const handleClose = () => {
    if (loadingInstances.size === 0) {
      setContextLength('')
      setContextPercentage('100')
      setDefaultContext(null)
      setLoadingErrors({})
      onClose()
    }
  }

  const getGPUGroupName = (instanceName: string): string | undefined => {
    if (!gpuConfig) return undefined

    const groupIndex = gpuConfig.instance_mapping[instanceName]
    if (groupIndex === undefined || groupIndex === -1) return undefined

    const group = gpuConfig.groups[groupIndex]
    return group?.name
  }

  const isModelLoadedOnInstance = (instanceName: string): boolean => {
    const instancesWithModel = runningModels[modelName] || []
    return instancesWithModel.includes(instanceName)
  }

  const hasAnyLoading = loadingInstances.size > 0

  if (!isOpen) return null

  return (
    <div className="flex fixed z-[1000] left-0 top-0 w-full h-full bg-black/50 items-center justify-center" onClick={handleClose}>
      <div className="bg-white p-0 rounded-xl w-[90%] max-w-[600px] shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-center px-8 py-6 border-b border-gray-200">
          <h3 className="text-xl font-semibold text-gray-900 m-0">Load Model: {modelName}</h3>
          <button
            className="text-gray-500 text-3xl font-bold cursor-pointer bg-transparent border-none p-0 w-8 h-8 flex items-center justify-center transition-colors hover:text-gray-700 disabled:opacity-30 disabled:cursor-not-allowed"
            onClick={handleClose}
            disabled={hasAnyLoading}
          >
            ×
          </button>
        </div>

        <div className="p-8">
          <div className="mb-6">
            <label className="block mb-2 font-medium text-gray-700 text-sm">Context Length (optional):</label>
            <select
              className="w-full p-3 border border-gray-300 rounded-md text-sm disabled:bg-gray-50 disabled:cursor-not-allowed"
              value={contextPercentage}
              onChange={(e) => setContextPercentage(e.target.value)}
              disabled={hasAnyLoading}
            >
              <option value="100">
                100% {defaultContext ? `(${formatNumber(defaultContext)})` : '(default)'}
              </option>
              {[90, 80, 70, 60, 50, 40, 30, 20, 10].map(percentage => (
                <option key={percentage} value={percentage.toString()}>
                  {percentage}% {defaultContext ? `(${formatNumber(Math.floor((defaultContext * percentage) / 100))})` : ''}
                </option>
              ))}
              {defaultContext && Math.floor((defaultContext * 10) / 100) > 200000 && 
                [9, 8, 7, 6, 5, 4, 3, 2, 1].map(percentage => (
                  <option key={percentage} value={percentage.toString()}>
                    {percentage}% {defaultContext ? `(${formatNumber(Math.floor((defaultContext * percentage) / 100))})` : ''}
                  </option>
                ))
              }
            </select>
            {defaultContext && (
              <small className="block mt-1 text-gray-600 text-xs">Model default context: {formatNumber(defaultContext)}</small>
            )}
          </div>

          <div className="mb-0">
            <label className="block mb-3 font-medium text-gray-700 text-sm">
              Available Instances:
            </label>

            {instances.length === 0 ? (
              <div className="text-center p-8 text-gray-500">
                No instances available
              </div>
            ) : (
              <div className="space-y-3 max-h-120 overflow-y-auto">
                {instances.map(instance => {
                  const status = instanceStatuses[instance.name]
                  const gpuGroupName = getGPUGroupName(instance.name)
                  const modelLoaded = isModelLoadedOnInstance(instance.name)
                  const isLoading = loadingInstances.has(instance.name)
                  const error = loadingErrors[instance.name]

                  return (
                    <div key={instance.name}>
                      <InstanceLoadButton
                        instanceName={instance.name}
                        gpuGroupName={gpuGroupName}
                        status={status?.status || 'offline'}
                        modelAlreadyLoaded={modelLoaded}
                        isLoading={isLoading}
                        anyInstanceLoading={loadingInstances.size > 0}
                        onLoad={handleInstanceLoad}
                      />
                      {error && (
                        <div className="mt-2 p-3 bg-red-50 border border-red-200 rounded-md">
                          <p className="text-sm text-red-600">Error: {error}</p>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        <div className="flex gap-4 justify-end px-8 py-6 border-t border-gray-200 bg-gray-50 rounded-b-xl">
          <button
            className="px-6 py-3 rounded-md text-sm font-medium cursor-pointer transition-all bg-white border border-gray-300 text-gray-700 hover:bg-gray-100 hover:border-gray-400 disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={handleClose}
            disabled={hasAnyLoading}
          >
            {hasAnyLoading ? 'Loading...' : 'Close'}
          </button>
        </div>
      </div>
    </div>
  )
}