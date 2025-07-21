'use client'

import { useState } from 'react'
import { fetchWithAuth } from '../lib/fetchWithAuth'

interface DeleteModelModalProps {
  isOpen: boolean
  modelName: string
  onClose: () => void
  onDeleted: () => void
}

export default function DeleteModelModal({
  isOpen,
  modelName,
  onClose,
  onDeleted
}: DeleteModelModalProps) {
  const [isDeleting, setIsDeleting] = useState(false)
  const [error, setError] = useState('')

  const handleDelete = async () => {
    setIsDeleting(true)
    setError('')

    try {
      const response = await fetchWithAuth('/ui/api/delete-model', {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ model: modelName })
      })

      if (response.ok) {
        onDeleted()
        onClose()
      } else {
        const errorData = await response.json()
        throw new Error(errorData.error || 'Failed to delete model')
      }
    } catch (error) {
      console.error('Error deleting model:', error)
      setError(error instanceof Error ? error.message : 'Failed to delete model')
    } finally {
      setIsDeleting(false)
    }
  }

  const handleClose = () => {
    if (!isDeleting) {
      setError('')
      onClose()
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-md w-full">
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Delete Model</h2>
            <button
              onClick={handleClose}
              disabled={isDeleting}
              className="text-gray-500 hover:text-gray-700 text-xl disabled:opacity-50"
            >
              ×
            </button>
          </div>
          
          <div className="mb-6">
            <p className="text-gray-700 mb-2">
              Are you sure you want to delete the model:
            </p>
            <p className="font-medium text-gray-900 bg-gray-50 p-2 rounded border">
              {modelName}
            </p>
            <p className="text-sm text-red-600 mt-2">
              This action cannot be undone. The model and all its data will be permanently deleted.
            </p>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
              {error}
            </div>
          )}

          <div className="flex justify-end space-x-3">
            <button
              onClick={handleClose}
              disabled={isDeleting}
              className="px-4 py-2 text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleDelete}
              disabled={isDeleting}
              className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50 flex items-center space-x-2"
            >
              {isDeleting && (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
              )}
              <span>{isDeleting ? 'Deleting...' : 'Delete'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}