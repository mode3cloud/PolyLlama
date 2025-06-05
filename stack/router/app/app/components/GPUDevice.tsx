'use client'

export interface GPUDeviceInfo {
  index: number;
  name: string;
  pci_bus: string;
}

interface GPUDeviceProps {
  device: GPUDeviceInfo;
}

export default function GPUDevice({ device }: GPUDeviceProps) {
  return (
    <div className="bg-gray-50 rounded-md p-4 border border-gray-200">
      <div className="flex justify-between items-center">
        <div>
          <div className="font-medium text-sm text-gray-800">{device.name}</div>
          <div className="text-xs text-gray-600 font-mono mt-1">PCI: {device.pci_bus}</div>
        </div>
        <div className="text-xs text-gray-500">
          Device {device.index}
        </div>
      </div>
    </div>
  )
}