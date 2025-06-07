'use client'

import { useState, useCallback, useMemo } from 'react'
import { Model, RunningModels, Instance, InstanceStatus } from '../types'
import ModelRow from './ModelRow'
import ModelBrowseModal from './ModelBrowseModal'
import ModelPullManager from './ModelPullManager'

interface ModelManagementProps {
  availableModels: Model[];
  runningModels: RunningModels;
  modelContexts: Record<string, number>;
  instances: Instance[];
  instanceStatuses: Record<string, InstanceStatus>;
  onLoadModel: (modelName: string) => void;
  onUnloadModel: (modelName: string) => void;
  onRefresh: () => void;
}

export default function ModelManagement({
  availableModels,
  runningModels,
  modelContexts,
  instances,
  instanceStatuses,
  onLoadModel,
  onUnloadModel,
  onRefresh
}: ModelManagementProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [currentFilter, setCurrentFilter] = useState<'all' | 'loaded' | 'available'>('all')
  const [expandedModels, setExpandedModels] = useState<Set<string>>(new Set())
  const [browseModalOpen, setBrowseModalOpen] = useState(false)
  const [pullManagerVisible, setPullManagerVisible] = useState(false)
  const [activePullIds, setActivePullIds] = useState<string[]>([])

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

  // Handle pull started from browse modal
  const handlePullStarted = useCallback((pullId: string, model: string, tag: string) => {
    setActivePullIds(prev => [...prev, pullId])
    setPullManagerVisible(true)
    // TODO: Add toast notification for pull started
  }, [])

  // Handle pull completed
  const handlePullCompleted = useCallback((model: string) => {
    // Refresh data to show new model
    onRefresh()
    // TODO: Add toast notification for pull completed
  }, [onRefresh])

  // Open browse modal
  const handleOpenBrowse = useCallback(() => {
    setBrowseModalOpen(true)
  }, [])

  // Close browse modal
  const handleCloseBrowse = useCallback(() => {
    setBrowseModalOpen(false)
  }, [])

  // Close pull manager
  const handleClosePullManager = useCallback(() => {
    setPullManagerVisible(false)
  }, [])

  return (
    <section className="my-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-semibold text-gray-900">Model Management</h2>
        <button
          onClick={handleOpenBrowse}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
        >
          Browse Models
        </button>
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

      {/* Browse Models Modal */}
      <ModelBrowseModal
        isOpen={browseModalOpen}
        instances={instances}
        instanceStatuses={instanceStatuses}
        onClose={handleCloseBrowse}
        onPullStarted={handlePullStarted}
      />

      {/* Pull Manager */}
      <ModelPullManager
        isVisible={pullManagerVisible}
        onClose={handleClosePullManager}
        activePullIds={activePullIds}
        onPullCompleted={handlePullCompleted}
      />
    </section>
  )
}