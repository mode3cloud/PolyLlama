'use client'

import { Instance, RunningModels } from '../types'

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
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
      <div className="bg-white rounded-xl p-6 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md">
        <div className="text-sm text-gray-600 mb-1 flex items-center gap-2">
          <span>🎮</span>
          <span>GPU Resources</span>
        </div>
        <div className="text-3xl font-bold text-gray-900">{totalGpuCount > 0 ? totalGpuCount : '0'}</div>
        <div className="text-sm text-gray-500 mt-2">
          {totalGpuCount > 0 ? `${totalGpuCount} GPU Groups Active` : 'No GPUs available'}
        </div>
      </div>

      <div className="bg-white rounded-xl p-6 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md">
        <div className="text-sm text-gray-600 mb-1 flex items-center gap-2">
          <span>🧠</span>
          <span>Active Models</span>
        </div>
        <div className="text-3xl font-bold text-gray-900">{activeModelCount}</div>
        <div className="text-sm text-gray-500 mt-2">{modelNames || 'No active models'}</div>
      </div>

      <div className="bg-white rounded-xl p-6 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md">
        <div className="text-sm text-gray-600 mb-1 flex items-center gap-2">
          <span>📊</span>
          <span>System Status</span>
        </div>
        <div className="text-3xl font-bold text-gray-900">{onlineInstances > 0 ? 'Online' : 'Offline'}</div>
        <div className="text-sm text-gray-500 mt-2">
          {onlineInstances}/{instances.length} instances healthy
        </div>
      </div>
    </div>
  )
}