'use client'

import { useState, useEffect } from 'react'
import { Model } from '../types'
import styles from './ModelRow.module.css'

interface ModelRowProps {
  model: Model;
  modelId: string;
  isLoaded: boolean;
  loadedOn: string[];
  contextSize?: number;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onLoad: () => void;
  onUnload: () => void;
}

export default function ModelRow({
  model,
  modelId,
  isLoaded,
  loadedOn,
  contextSize,
  isExpanded,
  onToggleExpand,
  onLoad,
  onUnload
}: ModelRowProps) {
  const [details, setDetails] = useState<any>(null)
  const [loadingDetails, setLoadingDetails] = useState(false)

  useEffect(() => {
    if (isExpanded && !details && !loadingDetails) {
      fetchModelDetails()
    }
  }, [isExpanded])

  const fetchModelDetails = async () => {
    setLoadingDetails(true)
    try {
      const response = await fetch('/api/ui/model-details', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: model.name })
      })
      
      if (response.ok) {
        const data = await response.json()
        setDetails(data)
      }
    } catch (error) {
      console.error('Error fetching model details:', error)
    } finally {
      setLoadingDetails(false)
    }
  }

  const formatSize = (bytes: number) => {
    if (!bytes) return '0 B'
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(1024))
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i]
  }

  return (
    <tr>
      <td colSpan={3}>
        <div className={styles.rowContent}>
          <div className={styles.mainInfo}>
            <div className={styles.header}>
              <button className={styles.expandBtn} onClick={onToggleExpand}>
                <span>{isExpanded ? '▼' : '▶'}</span>
              </button>
              <div>
                <div className={styles.modelName}>{model.name}</div>
                <div className={styles.modelSize}>{formatSize(model.size)}</div>
              </div>
            </div>
            <div className={styles.status}>
              {isLoaded ? (
                <>
                  <span className={`${styles.tag} ${styles.loaded}`}>
                    Loaded on {loadedOn.join(', ')}
                    {contextSize && <small className={styles.contextInfo}> (ctx: {contextSize})</small>}
                  </span>
                </>
              ) : (
                <span className={styles.tag}>Available</span>
              )}
            </div>
            <div className={styles.action}>
              {isLoaded ? (
                <button className={`${styles.actionBtn} ${styles.danger}`} onClick={onUnload}>
                  Unload
                </button>
              ) : (
                <button className={`${styles.actionBtn} ${styles.primary}`} onClick={onLoad}>
                  Load
                </button>
              )}
            </div>
          </div>

          {isExpanded && (
            <div className={styles.details}>
              {loadingDetails ? (
                <div className={styles.loading}>Loading model details...</div>
              ) : details ? (
                <div className={styles.detailsContent}>
                  {details.model_info && (
                    <div className={styles.detailSection}>
                      <h4>Model Information</h4>
                      <div className={styles.detailGrid}>
                        {details.details?.format && (
                          <div className={styles.detailItem}>
                            <span className={styles.detailLabel}>Format:</span> {details.details.format}
                          </div>
                        )}
                        {details.details?.family && (
                          <div className={styles.detailItem}>
                            <span className={styles.detailLabel}>Family:</span> {details.details.family}
                          </div>
                        )}
                        {details.details?.parameter_size && (
                          <div className={styles.detailItem}>
                            <span className={styles.detailLabel}>Parameters:</span> {details.details.parameter_size}
                          </div>
                        )}
                        {details.details?.quantization_level && (
                          <div className={styles.detailItem}>
                            <span className={styles.detailLabel}>Quantization:</span> {details.details.quantization_level}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                  
                  {details.template && (
                    <div className={styles.detailSection}>
                      <h4>Template</h4>
                      <pre className={styles.codePreview}>{details.template}</pre>
                    </div>
                  )}
                  
                  {details.parameters && (
                    <div className={styles.detailSection}>
                      <h4>Parameters</h4>
                      <pre className={styles.codePreview}>{details.parameters}</pre>
                    </div>
                  )}
                </div>
              ) : (
                <div className={styles.error}>Failed to load model details</div>
              )}
            </div>
          )}
        </div>
      </td>
    </tr>
  )
}