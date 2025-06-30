'use client'

interface EmailActionButtonsProps {
  selectedCount: number
  onArchive: () => void
  onDelete: () => void
  disabled: boolean
}

export default function EmailActionButtons({
  selectedCount,
  onArchive,
  onDelete,
  disabled
}: EmailActionButtonsProps) {
  return (
    <div className="px-4 py-3 bg-gray-50 border-b flex items-center justify-between">
      <span className="text-sm text-gray-600">
        {selectedCount} selected
      </span>
      
      <div className="flex space-x-2">
        <button
          onClick={onArchive}
          disabled={disabled}
          className="px-3 py-1.5 text-sm bg-white hover:bg-gray-100 border border-gray-300 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          📥 Archive
        </button>
        <button
          onClick={onDelete}
          disabled={disabled}
          className="px-3 py-1.5 text-sm bg-white hover:bg-red-50 border border-gray-300 text-red-600 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          🗑️ Delete
        </button>
      </div>
    </div>
  )
}