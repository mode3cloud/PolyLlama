'use client'

import { useState, useCallback, useEffect, useMemo } from 'react'
import { SearchModel, SearchModelsResponse, Instance, InstanceStatus, PullResponse } from '../types'
import { getApiUrl } from '../utils'

interface ModelBrowseModalProps {
  isOpen: boolean;
  instances: Instance[];
  instanceStatuses: Record<string, InstanceStatus>;
  onClose: () => void;
  onPullStarted: (pullId: string, model: string, tag: string) => void;
}

export default function ModelBrowseModal({
  isOpen,
  instances,
  instanceStatuses,
  onClose,
  onPullStarted
}: ModelBrowseModalProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchModel[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [expandedModels, setExpandedModels] = useState<Set<string>>(new Set())
  const [pullingModels, setPullingModels] = useState<Set<string>>(new Set())

  // Available instances for selection
  const availableInstances = useMemo(() => {
    return instances.filter(instance => {
      const status = instanceStatuses[instance.name]
      return status && status.status === 'online'
    })
  }, [instances, instanceStatuses])

  // Search for models from ollama.com
  const searchModels = useCallback(async (query: string) => {
    if (!query.trim()) {
      setSearchResults([])
      setHasSearched(false)
      return
    }

    setIsSearching(true)
    setSearchError(null)

    try {
      const response = await fetch(getApiUrl('/api/ui/search-models') + `?q=${encodeURIComponent(query)}`)
      
      if (!response.ok) {
        throw new Error(`Search failed: ${response.statusText}`)
      }

      const data: SearchModelsResponse = await response.json()
      
      if (!data.success) {
        throw new Error(data.error || 'Search failed')
      }

      setSearchResults(data.models)
      setHasSearched(true)
    } catch (error) {
      console.error('Error searching models:', error)
      setSearchError(error instanceof Error ? error.message : 'Failed to search models')
      setSearchResults([])
      setHasSearched(true)
    } finally {
      setIsSearching(false)
    }
  }, [])

  // Debounced search
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      searchModels(searchQuery)
    }, 500)

    return () => clearTimeout(timeoutId)
  }, [searchQuery, searchModels])

  // Toggle model expansion
  const handleToggleExpand = useCallback((modelName: string) => {
    setExpandedModels(prev => {
      const next = new Set(prev)
      if (next.has(modelName)) {
        next.delete(modelName)
      } else {
        next.add(modelName)
      }
      return next
    })
  }, [])

  // Pull a specific model tag
  const handlePullModel = useCallback(async (model: SearchModel, tag: string, instanceName?: string) => {
    const fullModelName = `${model.name}:${tag}`
    const pullKey = fullModelName

    setPullingModels(prev => new Set(prev).add(pullKey))

    try {
      const response = await fetch(getApiUrl('/api/ui/pull-model'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: model.name,
          tag: tag,
          instance: instanceName
        })
      })

      const data: PullResponse = await response.json()

      if (!data.success) {
        throw new Error(data.error || 'Failed to start model pull')
      }

      if (data.pull_id) {
        onPullStarted(data.pull_id, model.name, tag)
        // TODO: Add success toast notification
      }

    } catch (error) {
      console.error('Error pulling model:', error)
      // TODO: Add error toast notification
    } finally {
      setPullingModels(prev => {
        const next = new Set(prev)
        next.delete(pullKey)
        return next
      })
    }
  }, [onPullStarted])

  // Reset state when modal opens/closes
  useEffect(() => {
    if (!isOpen) {
      setSearchQuery('')
      setSearchResults([])
      setHasSearched(false)
      setSearchError(null)
      setExpandedModels(new Set())
      setPullingModels(new Set())
    }
  }, [isOpen])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-4xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">Browse Models</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl font-bold"
          >
            ×
          </button>
        </div>

        {/* Search Input */}
        <div className="p-6 border-b border-gray-100">
          <div className="relative">
            <input
              type="text"
              placeholder="Search models on ollama.com..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              autoFocus
            />
            {isSearching && (
              <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
              </div>
            )}
          </div>
        </div>

        {/* Search Results */}
        <div className="flex-1 overflow-y-auto p-6">
          {searchError && (
            <div className="text-center p-8">
              <div className="text-red-600 mb-2">Search Error</div>
              <div className="text-gray-600 text-sm">{searchError}</div>
            </div>
          )}

          {isSearching && !searchError && (
            <div className="text-center p-8">
              <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
              <div className="text-gray-600">Searching models...</div>
            </div>
          )}

          {!isSearching && !searchError && !hasSearched && (
            <div className="text-center p-8 text-gray-500">
              Enter a search term to find models from ollama.com
            </div>
          )}

          {!isSearching && !searchError && hasSearched && searchResults.length === 0 && (
            <div className="text-center p-8 text-gray-500">
              No models found for "{searchQuery}"
            </div>
          )}

          {!isSearching && !searchError && searchResults.length > 0 && (
            <div className="space-y-4">
              {searchResults.map((model) => (
                <div key={model.name} className="border border-gray-200 rounded-lg p-4 hover:border-gray-300 transition-colors">
                  {/* Model Header */}
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleToggleExpand(model.name)}
                        className="text-gray-600 hover:text-gray-800 p-1"
                      >
                        <span>{expandedModels.has(model.name) ? '▼' : '▶'}</span>
                      </button>
                      <div>
                        <h3 className="font-semibold text-gray-900">{model.title || model.name}</h3>
                        <div className="text-sm text-gray-600">{model.downloads} downloads</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {model.is_locally_available && (
                        <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
                          Partially Available
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Model Description */}
                  {model.description && (
                    <p className="text-gray-600 text-sm mb-3">{model.description}</p>
                  )}

                  {/* Model Tags */}
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium text-gray-700">Available Tags:</h4>
                    <div className="grid grid-cols-1 gap-2">
                      {/* Missing Tags (can be downloaded) */}
                      {model.missing_tags && model.missing_tags.map((tag) => {
                        const fullModelName = `${model.name}:${tag.name}`
                        const isPulling = pullingModels.has(fullModelName)
                        
                        return (
                          <div key={tag.name} className="flex items-center justify-between p-2 bg-blue-50 border border-blue-200 rounded">
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-blue-900">{model.name}:{tag.name}</span>
                              <span className="text-blue-700 text-xs">({tag.size})</span>
                            </div>
                            <div className="flex items-center gap-2">
                              {availableInstances.length > 1 && (
                                <select 
                                  className="text-xs border border-blue-300 rounded px-2 py-1"
                                  onChange={(e) => {
                                    if (e.target.value) {
                                      handlePullModel(model, tag.name, e.target.value)
                                      e.target.value = '' // Reset selection
                                    }
                                  }}
                                  disabled={isPulling}
                                >
                                  <option value="">Pull to...</option>
                                  {availableInstances.map(instance => (
                                    <option key={instance.name} value={instance.name}>
                                      {instance.name}
                                    </option>
                                  ))}
                                </select>
                              )}
                              <button
                                onClick={() => handlePullModel(model, tag.name)}
                                disabled={isPulling}
                                className="px-3 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                              >
                                {isPulling ? (
                                  <>
                                    <div className="w-3 h-3 border border-white border-t-transparent rounded-full animate-spin"></div>
                                    Pulling...
                                  </>
                                ) : (
                                  'Pull'
                                )}
                              </button>
                            </div>
                          </div>
                        )
                      })}

                      {/* Available Tags (already downloaded) */}
                      {model.available_tags && model.available_tags.map((tag) => (
                        <div key={tag.name} className="flex items-center justify-between p-2 bg-green-50 border border-green-200 rounded">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-green-900">{model.name}:{tag.name}</span>
                            <span className="text-green-700 text-xs">({tag.size})</span>
                          </div>
                          <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded">
                            Downloaded
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Expanded Details */}
                  {expandedModels.has(model.name) && (
                    <div className="mt-4 pt-4 border-t border-gray-200">
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <span className="font-medium text-gray-700">Model Page:</span>
                          <a 
                            href={model.url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="ml-2 text-blue-600 hover:text-blue-800 underline"
                          >
                            View on ollama.com
                          </a>
                        </div>
                        <div>
                          <span className="font-medium text-gray-700">Size:</span>
                          <span className="ml-2 text-gray-600">{model.size}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 bg-gray-50">
          <div className="flex justify-between items-center">
            <div className="text-sm text-gray-600">
              Search results from ollama.com • {searchResults.length} models found
            </div>
            <button
              onClick={onClose}
              className="px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}