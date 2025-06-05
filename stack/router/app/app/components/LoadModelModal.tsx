'use client'

import { useState, useEffect } from 'react'
import { Instance } from '../types'

interface LoadModelModalProps {
  isOpen: boolean;
  modelName: string;
  instances: Instance[];
  onClose: () => void;
  onConfirm: (modelName: string, instanceName: string, contextLength?: string) => Promise<void>;
}

export default function LoadModelModal({
  isOpen,
  modelName,
  instances,
  onClose,
  onConfirm
}: LoadModelModalProps) {
  const [selectedInstance, setSelectedInstance] = useState('')
  const [contextLength, setContextLength] = useState('')
  const [defaultContext, setDefaultContext] = useState<number | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (isOpen && modelName) {
      // Fetch model details to get default context
      fetchModelDetails()
    }
  }, [isOpen, modelName])

  const fetchModelDetails = async () => {
    try {
      const response = await fetch('/api/ui/model-details', {
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

  const handleConfirm = async () => {
    if (!selectedInstance) {
      alert('Please select an instance')
      return
    }

    setIsLoading(true)
    try {
      await onConfirm(modelName, selectedInstance, contextLength)
    } finally {
      setIsLoading(false)
    }
  }

  const handleClose = () => {
    if (!isLoading) {
      setSelectedInstance('')
      setContextLength('')
      setDefaultContext(null)
      onClose()
    }
  }

  if (!isOpen) return null

  return (
    <div className="flex fixed z-[1000] left-0 top-0 w-full h-full bg-black/50 items-center justify-center" onClick={handleClose}>
      <div className="bg-white p-0 rounded-xl w-[90%] max-w-[500px] shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-center px-8 py-6 border-b border-gray-200">
          <h3 className="text-xl font-semibold text-gray-900 m-0">Load Model</h3>
          <button 
            className="text-gray-500 text-3xl font-bold cursor-pointer bg-transparent border-none p-0 w-8 h-8 flex items-center justify-center transition-colors hover:text-gray-700 disabled:opacity-30 disabled:cursor-not-allowed"
            onClick={handleClose}
            disabled={isLoading}
          >
            ×
          </button>
        </div>

        <div className="p-8">
          <div className="mb-6">
            <label className="block mb-2 font-medium text-gray-700 text-sm">Model:</label>
            <input
              type="text"
              className="w-full p-3 border border-gray-300 rounded-md text-sm disabled:bg-gray-50 disabled:cursor-not-allowed"
              value={modelName}
              readOnly
              disabled={isLoading}
            />
          </div>

          <div className="mb-6">
            <label className="block mb-2 font-medium text-gray-700 text-sm">Instance:</label>
            <select
              className="w-full p-3 border border-gray-300 rounded-md text-sm disabled:bg-gray-50 disabled:cursor-not-allowed"
              value={selectedInstance}
              onChange={(e) => setSelectedInstance(e.target.value)}
              disabled={isLoading}
            >
              <option value="">Select instance...</option>
              {instances.map(instance => (
                <option key={instance.name} value={instance.name}>
                  {instance.name}
                </option>
              ))}
            </select>
          </div>

          <div className="mb-0">
            <label className="block mb-2 font-medium text-gray-700 text-sm">Context Length (optional):</label>
            <input
              type="number"
              className="w-full p-3 border border-gray-300 rounded-md text-sm disabled:bg-gray-50 disabled:cursor-not-allowed"
              placeholder={defaultContext ? `Default: ${defaultContext}` : 'e.g., 32768'}
              value={contextLength}
              onChange={(e) => setContextLength(e.target.value)}
              disabled={isLoading}
            />
            {defaultContext && (
              <small className="block mt-1 text-gray-600 text-xs">Model default context: {defaultContext}</small>
            )}
          </div>
        </div>

        <div className="flex gap-4 justify-end px-8 py-6 border-t border-gray-200 bg-gray-50 rounded-b-xl">
          <button
            className="px-6 py-3 rounded-md text-sm font-medium cursor-pointer transition-all bg-white border border-gray-300 text-gray-700 hover:bg-gray-100 hover:border-gray-400 disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={handleClose}
            disabled={isLoading}
          >
            Cancel
          </button>
          <button
            className="px-6 py-3 rounded-md text-sm font-medium cursor-pointer transition-all bg-primary text-white border-0 hover:bg-primary-dark disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={handleConfirm}
            disabled={isLoading}
          >
            {isLoading ? 'Loading...' : 'Load Model'}
          </button>
        </div>
      </div>
    </div>
  )
}