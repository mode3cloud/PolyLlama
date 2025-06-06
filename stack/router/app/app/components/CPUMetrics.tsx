'use client'

interface CPUMetricsData {
  memory_used: number
  memory_total: number
  temperature?: number
  is_cpu_instance: boolean
  timestamp: number
}

interface CPUMetricsProps {
  metrics?: CPUMetricsData
}

export default function CPUMetrics({ metrics }: CPUMetricsProps) {
  if (!metrics) {
    return (
      <div className="bg-gray-50 rounded-md p-4 border border-gray-200">
        <div className="text-xs text-gray-500 text-center py-2">
          Loading CPU metrics...
        </div>
      </div>
    )
  }

  const memoryPercent = (metrics.memory_used / metrics.memory_total) * 100

  return (
    <div className="bg-gray-50 rounded-md p-4 border border-gray-200">
      <div className="font-medium text-sm text-gray-800 mb-3">CPU Instance</div>
      
      <div className="space-y-2">
        {/* Memory Usage */}
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-gray-600">Memory</span>
            <span className="font-medium">
              {(metrics.memory_used / 1024).toFixed(1)}GB / {(metrics.memory_total / 1024).toFixed(1)}GB
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div 
              className="bg-blue-600 h-2 rounded-full transition-all duration-500"
              style={{ width: `${memoryPercent}%` }}
            />
          </div>
        </div>
        
        {/* Temperature if available */}
        {metrics.temperature && (
          <div className="text-xs text-gray-600">
            🌡️ {metrics.temperature.toFixed(0)}°C
          </div>
        )}
      </div>
    </div>
  )
}