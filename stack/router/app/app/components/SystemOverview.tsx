'use client'

import { Instance, RunningModels } from '../types'
import styles from './SystemOverview.module.css'

interface SystemOverviewProps {
  instances: Instance[];
  instanceStatuses: Record<string, any>;
  runningModels: RunningModels;
}

export default function SystemOverview({ instances, instanceStatuses, runningModels }: SystemOverviewProps) {
  const onlineInstances = Object.values(instanceStatuses).filter(i => i.status === 'online').length
  const totalGpuCount = onlineInstances
  const activeModelCount = Object.keys(runningModels).length
  const modelNames = Object.keys(runningModels).slice(0, 3).join(' • ')

  return (
    <div className={styles.overview}>
      <div className={styles.card}>
        <div className={styles.label}>
          <span>🖥️</span>
          <span>Total Instances</span>
        </div>
        <div className={styles.value}>{instances.length}</div>
        <div className={styles.details}>
          {onlineInstances} Online • {instances.length - onlineInstances} Offline
        </div>
      </div>

      <div className={styles.card}>
        <div className={styles.label}>
          <span>🎮</span>
          <span>GPU Resources</span>
        </div>
        <div className={styles.value}>{totalGpuCount > 0 ? totalGpuCount : '0'}</div>
        <div className={styles.details}>
          {totalGpuCount > 0 ? `${totalGpuCount} GPU Groups Active` : 'No GPUs available'}
        </div>
      </div>

      <div className={styles.card}>
        <div className={styles.label}>
          <span>🧠</span>
          <span>Active Models</span>
        </div>
        <div className={styles.value}>{activeModelCount}</div>
        <div className={styles.details}>{modelNames || 'No active models'}</div>
      </div>

      <div className={styles.card}>
        <div className={styles.label}>
          <span>📊</span>
          <span>System Status</span>
        </div>
        <div className={styles.value}>{onlineInstances > 0 ? 'Online' : 'Offline'}</div>
        <div className={styles.details}>
          {onlineInstances}/{instances.length} instances healthy
        </div>
      </div>
    </div>
  )
}