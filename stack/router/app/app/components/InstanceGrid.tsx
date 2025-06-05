'use client'

import { useCallback } from 'react'
import { Instance, RunningModels } from '../types'
import styles from './InstanceGrid.module.css'

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
    <section className={styles.section}>
      <div className={styles.header}>
        <h2 className={styles.title}>Instance Management</h2>
      </div>
      <div className={styles.grid}>
        {instances.map(instance => {
          const status = instanceStatuses[instance.name] || { status: 'offline', name: instance.name }
          const instanceModels = Object.keys(runningModels).filter(model =>
            runningModels[model].includes(instance.name)
          )
          const isOnline = status.status === 'online'
          const instanceNumber = instance.name.replace('polyllama', '')

          return (
            <div key={instance.name} className={styles.card}>
              <div className={styles.cardHeader}>
                <div className={styles.instanceName}>
                  <span className={`${styles.statusIndicator} ${!isOnline ? styles.offline : ''}`}></span>
                  <span>{instance.name}</span>
                </div>
                <span className={styles.instanceType}>GPU Group</span>
              </div>
              <div className={styles.cardBody}>
                <div className={styles.hardwareInfo}>
                  <div className={styles.gpuBadge}>GPU Group {instanceNumber}</div>
                </div>
                <div className={styles.stats}>
                  <div className={styles.statItem}>
                    <div className={styles.statLabel}>Status</div>
                    <div className={styles.statValue}>{isOnline ? 'Online' : 'Offline'}</div>
                  </div>
                  <div className={styles.statItem}>
                    <div className={styles.statLabel}>Models</div>
                    <div className={styles.statValue}>{instanceModels.length}</div>
                  </div>
                </div>
                <div className={styles.loadedModels}>
                  <div className={styles.loadedModelsHeader}>Loaded Models</div>
                  {instanceModels.length > 0 ? (
                    instanceModels.map(model => {
                      const contextInfo = modelContexts[model] ? ` (ctx: ${modelContexts[model]})` : ''
                      return (
                        <div key={model} className={styles.modelItem}>
                          <span className={`${styles.modelTag} ${styles.loaded}`}>
                            {model}
                            <small className={styles.contextInfo}>{contextInfo}</small>
                          </span>
                          <button 
                            className={styles.unloadBtn} 
                            onClick={() => handleUnloadModel(model, instance.name)}
                            title={`Unload ${model} from ${instance.name}`}
                          >
                            ×
                          </button>
                        </div>
                      )
                    })
                  ) : (
                    <span className={styles.modelTag}>No models loaded</span>
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