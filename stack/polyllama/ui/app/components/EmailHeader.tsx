'use client'

import { ChatModel } from '../types'

interface EmailHeaderProps {
  selectedModel: string
  models: ChatModel[]
  isLoading: boolean
  onModelChange: (model: string) => void
  onRefresh: () => void
  selectedCount: number
}

export default function EmailHeader({
  selectedModel,
  models,
  isLoading,
  onModelChange,
  onRefresh,
  selectedCount
}: EmailHeaderProps) {
  const getProviderIcon = (provider: string) => {
    switch (provider) {
      case 'ollama': return '🦙'
      case 'openai': return '🤖'
      case 'anthropic': return '🧠'
      case 'google': return '🔷'
      case 'groq': return '⚡'
      default: return '🔗'
    }
  }

  const groupedModels = models.reduce((acc, model) => {
    if (!acc[model.provider]) acc[model.provider] = []
    acc[model.provider].push(model)
    return acc
  }, {} as Record<string, ChatModel[]>)

  return (
    <div className="bg-white border-b px-4 py-3 flex items-center justify-between">
      <div className="flex items-center space-x-4">
        <h1 className="text-xl font-semibold">Email Assistant</h1>
        
        {/* Model Selector */}
        <select
          value={selectedModel}
          onChange={(e) => onModelChange(e.target.value)}
          disabled={isLoading}
          className="px-3 py-1.5 bg-gray-50 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
        >
          <option value="">Select AI Model</option>
          {Object.entries(groupedModels).map(([provider, providerModels]) => (
            <optgroup key={provider} label={`${getProviderIcon(provider)} ${provider}`}>
              {providerModels.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name}
                  {model.supports_vision && ' 👁️'}
                  {model.supports_tools && ' 🔧'}
                </option>
              ))}
            </optgroup>
          ))}
        </select>

        {selectedCount > 0 && (
          <span className="text-sm text-gray-600">
            {selectedCount} email{selectedCount !== 1 ? 's' : ''} selected
          </span>
        )}
      </div>

      <div className="flex items-center space-x-2">
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded-md transition-colors disabled:opacity-50"
          title="Refresh emails"
        >
          🔄 Refresh
        </button>
      </div>
    </div>
  )
}