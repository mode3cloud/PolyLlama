'use client'

export interface GPUDeviceInfo {
  index: number;
  name: string;
  pci_bus: string;
}

interface GPUMetrics {
  index: number
  memory_used: number
  memory_total: number
  gpu_utilization: number
  temperature: number
  power_draw: number
  timestamp: number
}

interface GPUDeviceProps {
  device: GPUDeviceInfo;
  deviceMetrics?: GPUMetrics;
}

export default function GPUDevice({ device, deviceMetrics }: GPUDeviceProps) {
  
  // Calculate percentages and colors
  const memoryPercent = deviceMetrics 
    ? (deviceMetrics.memory_used / deviceMetrics.memory_total) * 100 
    : 0
    
  const getTemperatureColor = (temp?: number) => {
    if (!temp) return 'text-gray-500'
    if (temp < 60) return 'text-green-600'
    if (temp < 75) return 'text-yellow-600'
    return 'text-red-600'
  }
  
  const getUtilizationColor = (util?: number) => {
    if (!util) return 'bg-gray-200'
    if (util < 50) return 'bg-green-500'
    if (util < 80) return 'bg-yellow-500'
    return 'bg-red-500'
  }

  return (
    <div className="bg-gray-50 rounded-md p-4 border border-gray-200">
      <div className="flex justify-between items-start mb-3">
        <div>
          <div className="font-medium text-sm text-gray-800">{device.name}</div>
          <div className="text-xs text-gray-600 font-mono mt-1">PCI: {device.pci_bus}</div>
        </div>
        <div className="text-xs text-gray-500">
          Device {device.index}
        </div>
      </div>
      
      {deviceMetrics ? (
        <div className="space-y-2 mt-3">
          {/* VRAM Usage */}
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-gray-600">VRAM</span>
              <span className="font-medium">
                {(deviceMetrics.memory_used / 1024).toFixed(1)}GB / {(deviceMetrics.memory_total / 1024).toFixed(1)}GB
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                style={{ width: `${memoryPercent}%` }}
              />
            </div>
          </div>
          
          {/* GPU Utilization */}
          <div className="flex justify-between items-center">
            <span className="text-xs text-gray-600">GPU</span>
            <div className="flex items-center gap-2">
              <div className={`w-16 h-1.5 rounded-full ${getUtilizationColor(deviceMetrics.gpu_utilization)}`}>
                <div 
                  className="h-full bg-current rounded-full"
                  style={{ width: `${deviceMetrics.gpu_utilization}%` }}
                />
              </div>
              <span className="text-xs font-medium">{deviceMetrics.gpu_utilization}%</span>
            </div>
          </div>
          
          {/* Temperature & Power */}
          <div className="flex justify-between text-xs">
            <span className={getTemperatureColor(deviceMetrics.temperature)}>
              🌡️ {deviceMetrics.temperature}°C
            </span>
            <span className="text-gray-600">
              ⚡ {deviceMetrics.power_draw?.toFixed(0)}W
            </span>
          </div>
        </div>
      ) : (
        <div className="text-xs text-gray-500 text-center py-2">
          Loading metrics...
        </div>
      )}
    </div>
  )
}