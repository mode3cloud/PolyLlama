'use client'

import { useState } from 'react'
import { useGPUMetrics } from '../hooks/useGPUMetrics'

interface InstanceLoadButtonProps {
  instanceName: string;
  gpuGroupName?: string;
  status: 'online' | 'offline';
  modelAlreadyLoaded: boolean;
  isLoading: boolean;
  onLoad: (instanceName: string) => void;
}

export default function InstanceLoadButton({
  instanceName,
  gpuGroupName,
  status,
  modelAlreadyLoaded,
  isLoading,
  onLoad
}: InstanceLoadButtonProps) {
  const { metrics } = useGPUMetrics(instanceName)

  const getMemoryInfo = () => {
    if (!metrics) return null
    
    if (metrics.type === 'gpu' && metrics.devices && metrics.devices.length > 0) {
      // For GPU instances, sum up memory across all devices
      const totalUsed = metrics.devices.reduce((sum, device) => sum + device.memory_used, 0)
      const totalAvailable = metrics.devices.reduce((sum, device) => sum + device.memory_total, 0)
      const freeMemory = totalAvailable - totalUsed
      
      return {
        used: totalUsed,
        total: totalAvailable,
        free: freeMemory,
        unit: 'MB',
        type: 'GPU'
      }
    } else if (metrics.type === 'cpu' && metrics.cpu_metrics) {
      // For CPU instances, show system memory
      const totalUsed = metrics.cpu_metrics.memory_used
      const totalAvailable = metrics.cpu_metrics.memory_total
      const freeMemory = totalAvailable - totalUsed
      
      return {
        used: totalUsed,
        total: totalAvailable,
        free: freeMemory,
        unit: 'MB',
        type: 'CPU'
      }
    }
    
    return null
  }

  const formatMemory = (mb: number) => {
    if (mb >= 1024) {
      return `${(mb / 1024).toFixed(1)}GB`
    }
    return `${mb}MB`
  }

  const memoryInfo = getMemoryInfo()

  const getStatusColor = () => {
    if (status === 'offline') return 'text-red-600 bg-red-50'
    if (modelAlreadyLoaded) return 'text-blue-600 bg-blue-50'
    return 'text-green-600 bg-green-50'
  }

  const getStatusText = () => {
    if (status === 'offline') return 'Offline'
    if (modelAlreadyLoaded) return 'Model Loaded'
    return 'Online'
  }

  const isDisabled = status === 'offline' || modelAlreadyLoaded || isLoading

  return (
    <div className="border border-gray-200 rounded-lg p-4 mb-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          <h4 className="font-medium text-gray-900">{instanceName}</h4>
          <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor()}`}>
            {getStatusText()}
          </span>
        </div>
        {gpuGroupName && (
          <span className="text-sm text-gray-600">
            {gpuGroupName}
          </span>
        )}
      </div>

      {memoryInfo && (
        <div className="mb-3">
          <div className="flex items-center justify-between text-sm text-gray-600 mb-1">
            <span>{memoryInfo.type} Memory</span>
            <span>{formatMemory(memoryInfo.free)} / {formatMemory(memoryInfo.total)} free</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div 
              className="bg-blue-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${(memoryInfo.used / memoryInfo.total) * 100}%` }}
            />
          </div>
        </div>
      )}

      <button
        className={`w-full py-2 px-4 rounded-md text-sm font-medium transition-all ${
          isDisabled
            ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
            : 'bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800'
        }`}
        onClick={() => onLoad(instanceName)}
        disabled={isDisabled}
      >
        {isLoading ? (
          <div className="flex items-center justify-center gap-2">
            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Loading...
          </div>
        ) : modelAlreadyLoaded ? (
          'Already Loaded'
        ) : status === 'offline' ? (
          'Instance Offline'
        ) : (
          'Load on this instance'
        )}
      </button>
    </div>
  )
}