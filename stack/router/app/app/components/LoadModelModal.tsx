'use client'

import { useState, useEffect } from 'react'
import { Instance } from '../types'
import styles from './LoadModelModal.module.css'

interface LoadModelModalProps {
  isOpen: boolean;
  modelName: string;
  instances: Instance[];
  onClose: () => void;
  onConfirm: (modelName: string, instanceName: string, contextLength?: string) => Promise<void>;
}

export default function LoadModelModal({
  isOpen,
  modelName,
  instances,
  onClose,
  onConfirm
}: LoadModelModalProps) {
  const [selectedInstance, setSelectedInstance] = useState('')
  const [contextLength, setContextLength] = useState('')
  const [defaultContext, setDefaultContext] = useState<number | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (isOpen && modelName) {
      // Fetch model details to get default context
      fetchModelDetails()
    }
  }, [isOpen, modelName])

  const fetchModelDetails = async () => {
    try {
      const response = await fetch('/api/ui/model-details', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelName })
      })

      if (response.ok) {
        const data = await response.json()
        
        // Extract default context size from model info
        if (data.model_info && data.details && data.details.family) {
          const contextKey = data.details.family + '.context_length'
          const contextValue = data.model_info[contextKey]
          if (contextValue) {
            setDefaultContext(contextValue)
          }
        }
      }
    } catch (error) {
      console.error('Error fetching model details:', error)
    }
  }

  const handleConfirm = async () => {
    if (!selectedInstance) {
      alert('Please select an instance')
      return
    }

    setIsLoading(true)
    try {
      await onConfirm(modelName, selectedInstance, contextLength)
    } finally {
      setIsLoading(false)
    }
  }

  const handleClose = () => {
    if (!isLoading) {
      setSelectedInstance('')
      setContextLength('')
      setDefaultContext(null)
      onClose()
    }
  }

  if (!isOpen) return null

  return (
    <div className={styles.modal} onClick={handleClose}>
      <div className={styles.content} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h3 className={styles.title}>Load Model</h3>
          <button 
            className={styles.closeBtn} 
            onClick={handleClose}
            disabled={isLoading}
          >
            ×
          </button>
        </div>

        <div className={styles.body}>
          <div className={styles.formGroup}>
            <label className={styles.label}>Model:</label>
            <input
              type="text"
              className={styles.input}
              value={modelName}
              readOnly
              disabled={isLoading}
            />
          </div>

          <div className={styles.formGroup}>
            <label className={styles.label}>Instance:</label>
            <select
              className={styles.input}
              value={selectedInstance}
              onChange={(e) => setSelectedInstance(e.target.value)}
              disabled={isLoading}
            >
              <option value="">Select instance...</option>
              {instances.map(instance => (
                <option key={instance.name} value={instance.name}>
                  {instance.name}
                </option>
              ))}
            </select>
          </div>

          <div className={styles.formGroup}>
            <label className={styles.label}>Context Length (optional):</label>
            <input
              type="number"
              className={styles.input}
              placeholder={defaultContext ? `Default: ${defaultContext}` : 'e.g., 32768'}
              value={contextLength}
              onChange={(e) => setContextLength(e.target.value)}
              disabled={isLoading}
            />
            {defaultContext && (
              <small className={styles.hint}>Model default context: {defaultContext}</small>
            )}
          </div>
        </div>

        <div className={styles.footer}>
          <button
            className={styles.btnSecondary}
            onClick={handleClose}
            disabled={isLoading}
          >
            Cancel
          </button>
          <button
            className={styles.btnPrimary}
            onClick={handleConfirm}
            disabled={isLoading}
          >
            {isLoading ? 'Loading...' : 'Load Model'}
          </button>
        </div>
      </div>
    </div>
  )
}