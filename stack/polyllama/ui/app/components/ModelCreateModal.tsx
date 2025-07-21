'use client'

import { useState } from 'react'
import { fetchWithAuth } from '../lib/fetchWithAuth'

interface ModelCreateModalProps {
  isOpen: boolean
  onClose: () => void
  onCreated: () => void
}

const DEFAULT_BASE_MODEL = `hf.co/unsloth/Llama-4-Scout-17B-16E-Instruct-GGUF:Q3_K_XL`
const DEFAULT_MODELFILE = `PARAMETER num_ctx 122880`

export default function ModelCreateModal({
  isOpen,
  onClose,
  onCreated
}: ModelCreateModalProps) {
  const [modelName, setModelName] = useState('')
  const [baseModel, setBaseModel] = useState(DEFAULT_BASE_MODEL)
  const [modelfile, setModelfile] = useState(DEFAULT_MODELFILE)
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState('')
  const [creationStatus, setCreationStatus] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!modelName.trim()) {
      setError('Model name is required')
      return
    }

    if (!baseModel.trim()) {
      setError('Base model is required')
      return
    }

    setIsCreating(true)
    setError('')
    setCreationStatus('Starting model creation...')

    try {
      const response = await fetchWithAuth('/ui/api/create-model', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: modelName.trim(),
          from: baseModel.trim(),
          modelfile: modelfile.trim()
        })
      })

      if (response.ok) {
        setCreationStatus('Model created successfully!')
        setTimeout(() => {
          onCreated()
          handleClose()
        }, 2000)
      } else {
        const errorData = await response.json()
        throw new Error(errorData.error || 'Failed to create model')
      }
    } catch (error) {
      console.error('Error creating model:', error)
      setError(error instanceof Error ? error.message : 'Failed to create model')
      setCreationStatus('')
    } finally {
      setIsCreating(false)
    }
  }

  const handleClose = () => {
    if (!isCreating) {
      setModelName('')
      setBaseModel(DEFAULT_BASE_MODEL)
      setModelfile(DEFAULT_MODELFILE)
      setError('')
      setCreationStatus('')
      onClose()
    }
  }

  const handleModelfileChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setModelfile(e.target.value)
    setError('')
  }

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setModelName(e.target.value)
    setError('')
  }

  const handleBaseModelChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setBaseModel(e.target.value)
    setError('')
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold">Create Custom Model</h2>
            <button
              onClick={handleClose}
              disabled={isCreating}
              className="text-gray-500 hover:text-gray-700 text-2xl disabled:opacity-50"
            >
              ×
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-6">
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Model Name
            </label>
            <input
              type="text"
              value={modelName}
              onChange={handleNameChange}
              disabled={isCreating}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
              placeholder="Enter model name (e.g., my-custom-model)"
              required
            />
          </div>

          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Base Model
            </label>
            <input
              type="text"
              value={baseModel}
              onChange={handleBaseModelChange}
              disabled={isCreating}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
              placeholder="Enter base model (e.g., llama3:latest or hf.co/model-name)"
              required
            />
            <p className="text-sm text-gray-500 mt-2">
              The base model to build from. Can be a local model name or a Hugging Face model path.
            </p>
          </div>

          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Modelfile Content (Optional)
            </label>
            <textarea
              value={modelfile}
              onChange={handleModelfileChange}
              disabled={isCreating}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 font-mono text-sm"
              rows={8}
              placeholder="Enter additional Modelfile content..."
            />
            <p className="text-sm text-gray-500 mt-2">
              Additional parameters and configurations. Use PARAMETER for model parameters,
              SYSTEM for system prompts, and TEMPLATE for custom templates.
            </p>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
              {error}
            </div>
          )}

          {creationStatus && (
            <div className="mb-4 p-3 bg-blue-100 border border-blue-400 text-blue-700 rounded">
              {creationStatus}
            </div>
          )}

          <div className="flex justify-end space-x-4">
            <button
              type="button"
              onClick={handleClose}
              disabled={isCreating}
              className="px-4 py-2 text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isCreating}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 flex items-center space-x-2"
            >
              {isCreating && (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
              )}
              <span>{isCreating ? 'Creating...' : 'Create Model'}</span>
            </button>
          </div>
        </form>

        <div className="p-6 bg-gray-50 border-t">
          <h3 className="text-sm font-medium text-gray-700 mb-2">Modelfile Examples:</h3>
          <div className="text-sm text-gray-600 space-y-1">
            <p><strong>PARAMETER:</strong> Set parameters (e.g., <code>PARAMETER num_ctx 122880</code>)</p>
            <p><strong>SYSTEM:</strong> Add system prompt (e.g., <code>SYSTEM You are a helpful assistant.</code>)</p>
            <p><strong>TEMPLATE:</strong> Define prompt template</p>
          </div>
          <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded">
            <h4 className="text-sm font-medium text-blue-800 mb-1">Note:</h4>
            <p className="text-sm text-blue-700">
              The base model is specified separately above. The modelfile should only contain additional
              parameters, system prompts, and templates - not the FROM directive.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}