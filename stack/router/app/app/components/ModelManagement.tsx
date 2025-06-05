'use client'

import { useState, useCallback, useMemo } from 'react'
import { Model, RunningModels } from '../types'
import ModelRow from './ModelRow'
import styles from './ModelManagement.module.css'

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
    <section className={styles.section}>
      <div className={styles.header}>
        <h2 className={styles.title}>Model Management</h2>
      </div>
      <div className={styles.content}>
        <div className={styles.controls}>
          <input
            type="text"
            className={styles.searchInput}
            placeholder="Search models..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <button
            className={`${styles.filterBtn} ${currentFilter === 'all' ? styles.active : ''}`}
            onClick={() => setCurrentFilter('all')}
          >
            All Models
          </button>
          <button
            className={`${styles.filterBtn} ${currentFilter === 'loaded' ? styles.active : ''}`}
            onClick={() => setCurrentFilter('loaded')}
          >
            Loaded
          </button>
          <button
            className={`${styles.filterBtn} ${currentFilter === 'available' ? styles.active : ''}`}
            onClick={() => setCurrentFilter('available')}
          >
            Available
          </button>
        </div>

        <table className={styles.table}>
          <thead>
            <tr>
              <th>Models</th>
            </tr>
          </thead>
          <tbody>
            {filteredModels.length === 0 ? (
              <tr>
                <td className={styles.noResults}>No models found</td>
              </tr>
            ) : (
              filteredModels.map((model, index) => (
                <ModelRow
                  key={model.name}
                  model={model}
                  modelId={`model-${index}`}
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