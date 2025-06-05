'use client'

import { useState, useCallback, useMemo } from 'react'
import { Model, RunningModels } from '../types'
import ModelRow from './ModelRow'

interface ModelManagementProps {
  availableModels: Model[];
  runningModels: RunningModels;
  modelContexts: Record<string, number>;
  onLoadModel: (modelName: string) => void;
  onUnloadModel: (modelName: string) => void;
}

export default function ModelManagement({
  availableModels,
  runningModels,
  modelContexts,
  onLoadModel,
  onUnloadModel
}: ModelManagementProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [currentFilter, setCurrentFilter] = useState<'all' | 'loaded' | 'available'>('all')
  const [expandedModels, setExpandedModels] = useState<Set<string>>(new Set())

  const filteredModels = useMemo(() => {
    return availableModels.filter(model => {
      const matchesSearch = model.name.toLowerCase().includes(searchQuery.toLowerCase())
      const isLoaded = runningModels.hasOwnProperty(model.name)

      switch (currentFilter) {
        case 'loaded':
          return matchesSearch && isLoaded
        case 'available':
          return matchesSearch && !isLoaded
        default:
          return matchesSearch
      }
    }).sort((a, b) => a.name.localeCompare(b.name))
  }, [availableModels, runningModels, searchQuery, currentFilter])

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

  return (
    <section className="mb-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-semibold text-gray-900">Model Management</h2>
      </div>
      <div className="bg-white rounded-xl p-8 shadow-sm">
        <div className="flex gap-4 mb-6 flex-wrap">
          <input
            type="text"
            className="flex-1 min-w-[250px] px-4 py-3 border border-gray-300 rounded-md text-sm"
            placeholder="Search local models..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <button
            className={`px-5 py-3 bg-white border border-gray-300 rounded-md cursor-pointer text-sm flex items-center gap-2 transition-all hover:bg-gray-50 hover:border-gray-400 ${currentFilter === 'all' ? 'bg-gradient-to-r from-gray-700 to-gray-800 text-white border-primary hover:bg-primary-dark hover:border-primary-dark' : ''
              }`}
            onClick={() => setCurrentFilter('all')}
          >
            All Models
          </button>
          <button
            className={`px-5 py-3 bg-white border border-gray-300 rounded-md cursor-pointer text-sm flex items-center gap-2 transition-all hover:bg-gray-50 hover:border-gray-400 ${currentFilter === 'loaded' ? 'bg-gradient-to-r from-gray-700 to-gray-800 text-white border-primary hover:bg-primary-dark hover:border-primary-dark' : ''
              }`}
            onClick={() => setCurrentFilter('loaded')}
          >
            Loaded
          </button>
          <button
            className={`px-5 py-3 bg-white border border-gray-300 rounded-md cursor-pointer text-sm flex items-center gap-2 transition-all hover:bg-gray-50 hover:border-gray-400 ${currentFilter === 'available' ? 'bg-gradient-to-r from-gray-700 to-gray-800 text-white border-primary hover:bg-primary-dark hover:border-primary-dark' : ''
              }`}
            onClick={() => setCurrentFilter('available')}
          >
            Available
          </button>
        </div>

        <table className="w-full border-collapse">
          <thead>
            <tr>
              <th className="text-left px-4 py-3 border-b-2 border-gray-200 font-semibold text-gray-700 text-sm">Models</th>
            </tr>
          </thead>
          <tbody>
            {filteredModels.length === 0 ? (
              <tr>
                <td className="text-center p-8 text-gray-500">No models found</td>
              </tr>
            ) : (
              filteredModels.map((model) => (
                <ModelRow
                  key={model.name}
                  model={model}
                  isLoaded={runningModels.hasOwnProperty(model.name)}
                  loadedOn={runningModels[model.name] || []}
                  contextSize={modelContexts[model.name]}
                  isExpanded={expandedModels.has(model.name)}
                  onToggleExpand={() => handleToggleExpand(model.name)}
                  onLoad={() => onLoadModel(model.name)}
                  onUnload={() => onUnloadModel(model.name)}
                />
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}