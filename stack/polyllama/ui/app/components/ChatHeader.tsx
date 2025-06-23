'use client'

import { ChatModel } from '../types'

interface ChatHeaderProps {
  selectedModel: string
  models: ChatModel[]
  isLoading: boolean
  showSidebar: boolean
  temperature: number
  audioEnabled: boolean
  onModelChange: (model: string) => void
  onToggleSidebar: () => void
  onClearChat: () => void
  onExportChat: () => void
  onTemperatureChange: (temp: number) => void
  onToggleAudio: () => void
  hasMessages: boolean
}

export default function ChatHeader({
  selectedModel,
  models,
  isLoading,
  showSidebar,
  temperature,
  audioEnabled,
  onModelChange,
  onToggleSidebar,
  onClearChat,
  onExportChat,
  onTemperatureChange,
  onToggleAudio,
  hasMessages
}: ChatHeaderProps) {
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
    <div className="bg-white border-b border-gray-200 p-4 flex-shrink-0">
      <div className="flex items-center justify-between max-w-4xl mx-auto">
        <div className="flex items-center gap-4">
          <button
            onClick={onToggleSidebar}
            className="px-3 py-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
            title={showSidebar ? 'Hide sidebar' : 'Show sidebar'}
          >
            {showSidebar ? '◀' : '▶'}
          </button>

          <select
            value={selectedModel}
            onChange={(e) => onModelChange(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg bg-white text-sm min-w-[200px]"
            disabled={isLoading}
          >
            <option value="">Select a model...</option>
            {Object.entries(groupedModels).map(([provider, providerModels]) => (
              <optgroup key={provider} label={`${getProviderIcon(provider)} ${provider.charAt(0).toUpperCase() + provider.slice(1)}`}>
                {providerModels.map(model => (
                  <option key={model.id} value={model.id}>
                    {model.name}{model.supports_vision ? ' 👁️' : ''}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>

          {selectedModel && (
            <span className="text-sm text-gray-600">
              Provider: {models.find(m => m.id === selectedModel)?.provider || 'Unknown'}
              {models.find(m => m.id === selectedModel)?.supports_vision && ' 👁️'}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Temperature control */}
          <div className="flex items-center gap-2 mr-2">
            <label htmlFor="temperature" className="text-sm text-gray-600">
              Temp:
            </label>
            <input
              id="temperature"
              type="range"
              min="0"
              max="2"
              step="0.1"
              value={temperature}
              onChange={(e) => onTemperatureChange(parseFloat(e.target.value))}
              className="w-20 h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
            <span className="text-sm text-gray-600 w-8 text-right">
              {temperature.toFixed(1)}
            </span>
          </div>

          <div className="border-l border-gray-300 h-6 mx-1" />

          <button
            onClick={onToggleAudio}
            className={`px-3 py-2 text-sm rounded-lg transition-colors ${
              audioEnabled 
                ? 'bg-blue-100 text-blue-700 hover:bg-blue-200' 
                : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
            }`}
            title={audioEnabled ? 'Disable audio responses' : 'Enable audio responses'}
          >
            {audioEnabled ? '🔊' : '🔇'} Audio
          </button>

          <button
            onClick={onClearChat}
            className="px-3 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
            disabled={isLoading}
          >
            Clear
          </button>
          <button
            onClick={onExportChat}
            className="px-3 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
            disabled={!hasMessages}
          >
            Export
          </button>
        </div>
      </div>
    </div>
  )
}