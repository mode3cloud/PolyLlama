'use client'

import { useState, useEffect, useCallback } from 'react'
import { PullStatus, PullStatusesResponse } from '../types'
import { getApiUrl } from '../utils'

interface ModelPullManagerProps {
  isVisible: boolean;
  onClose: () => void;
  activePullIds: string[];
  onPullCompleted: (model: string) => void;
}

export default function ModelPullManager({
  isVisible,
  onClose,
  activePullIds,
  onPullCompleted
}: ModelPullManagerProps) {
  const [pullStatuses, setPullStatuses] = useState<PullStatus[]>([])
  const [isLoading, setIsLoading] = useState(false)

  // Fetch all pull statuses
  const fetchPullStatuses = useCallback(async () => {
    try {
      setIsLoading(true)
      const response = await fetch(getApiUrl('/api/ui/pull-statuses'))
      
      if (!response.ok) {
        throw new Error(`Failed to fetch pull statuses: ${response.statusText}`)
      }

      const data: PullStatusesResponse = await response.json()
      
      if (data.success) {
        setPullStatuses(data.pull_statuses)
        
        // Check for completed pulls and notify parent
        data.pull_statuses.forEach(status => {
          if (status.status === 'completed' && activePullIds.includes(status.id)) {
            onPullCompleted(status.model)
          }
        })
      }
    } catch (error) {
      console.error('Error fetching pull statuses:', error)
    } finally {
      setIsLoading(false)
    }
  }, [activePullIds, onPullCompleted])

  // Auto-refresh pull statuses
  useEffect(() => {
    if (isVisible && activePullIds.length > 0) {
      fetchPullStatuses()
      
      // Refresh every 2 seconds while there are active pulls
      const interval = setInterval(fetchPullStatuses, 2000)
      
      return () => clearInterval(interval)
    }
  }, [isVisible, activePullIds, fetchPullStatuses])

  // Filter to show only relevant pulls
  const relevantPulls = pullStatuses.filter(status => 
    activePullIds.includes(status.id) || 
    ['starting', 'in_progress'].includes(status.status)
  )

  // Format elapsed time
  const formatElapsedTime = (startTime: number) => {
    const elapsed = Math.floor(Date.now() / 1000) - startTime
    const minutes = Math.floor(elapsed / 60)
    const seconds = elapsed % 60
    
    if (minutes > 0) {
      return `${minutes}m ${seconds}s`
    }
    return `${seconds}s`
  }

  // Get status color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-green-600 bg-green-100'
      case 'failed':
      case 'timeout':
        return 'text-red-600 bg-red-100'
      case 'in_progress':
        return 'text-blue-600 bg-blue-100'
      case 'starting':
        return 'text-yellow-600 bg-yellow-100'
      default:
        return 'text-gray-600 bg-gray-100'
    }
  }

  if (!isVisible || relevantPulls.length === 0) {
    return null
  }

  return (
    <div className="fixed bottom-4 right-4 w-96 bg-white border border-gray-200 rounded-lg shadow-lg z-40">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <h3 className="font-semibold text-gray-900">Model Downloads</h3>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600"
        >
          ×
        </button>
      </div>

      {/* Pull Status List */}
      <div className="max-h-80 overflow-y-auto">
        {isLoading && relevantPulls.length === 0 ? (
          <div className="p-4 text-center text-gray-500">
            <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
            Loading pull statuses...
          </div>
        ) : (
          <div className="space-y-3 p-4">
            {relevantPulls.map((pullStatus) => (
              <div key={pullStatus.id} className="border border-gray-200 rounded-lg p-3">
                {/* Model Name and Instance */}
                <div className="flex items-center justify-between mb-2">
                  <div className="flex-1">
                    <div className="font-medium text-gray-900 text-sm">
                      {pullStatus.model}
                    </div>
                    <div className="text-xs text-gray-600">
                      → {pullStatus.instance}
                    </div>
                  </div>
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(pullStatus.status)}`}>
                    {pullStatus.status}
                  </span>
                </div>

                {/* Progress Bar */}
                {pullStatus.status === 'in_progress' && (
                  <div className="mb-2">
                    <div className="bg-gray-200 rounded-full h-2">
                      <div 
                        className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${pullStatus.progress}%` }}
                      ></div>
                    </div>
                    <div className="flex justify-between text-xs text-gray-600 mt-1">
                      <span>{pullStatus.stage}</span>
                      <span>{pullStatus.progress}%</span>
                    </div>
                  </div>
                )}

                {/* Status Message */}
                <div className="text-xs text-gray-600">
                  {pullStatus.status === 'starting' && (
                    <span>Initializing download...</span>
                  )}
                  {pullStatus.status === 'in_progress' && (
                    <span>Downloading • {formatElapsedTime(pullStatus.started_at)} elapsed</span>
                  )}
                  {pullStatus.status === 'completed' && (
                    <span className="text-green-600">
                      ✓ Downloaded in {formatElapsedTime(pullStatus.started_at)}
                    </span>
                  )}
                  {pullStatus.status === 'failed' && (
                    <span className="text-red-600">
                      ✗ Failed: {pullStatus.error || 'Unknown error'}
                    </span>
                  )}
                  {pullStatus.status === 'timeout' && (
                    <span className="text-red-600">
                      ⏱ Timeout after {formatElapsedTime(pullStatus.started_at)}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-gray-200 bg-gray-50 text-xs text-gray-600">
        {relevantPulls.filter(p => ['starting', 'in_progress'].includes(p.status)).length > 0 ? (
          <span>Downloads in progress • Auto-refreshing every 2s</span>
        ) : (
          <span>All downloads completed</span>
        )}
      </div>
    </div>
  )
}