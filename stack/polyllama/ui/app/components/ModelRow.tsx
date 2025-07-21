'use client'

import { useState, useEffect } from 'react'
import { Model } from '../types'

interface ModelRowProps {
  model: Model;
  isLoaded: boolean;
  loadedOn: string[];
  isExpanded: boolean;
  onToggleExpand: () => void;
  onLoad: () => void;
  onUnload: () => void;
  onDelete: () => void;
}

export default function ModelRow({
  model,
  isLoaded,
  loadedOn,
  isExpanded,
  onToggleExpand,
  onLoad,
  onUnload,
  onDelete
}: ModelRowProps) {
  interface ModelDetails {
    model_info?: Record<string, unknown>
    details?: {
      format?: string
      family?: string
      parameter_size?: string
      quantization_level?: string
    }
    template?: string
    system?: string
    parameters?: string
  }
  
  const [details, setDetails] = useState<ModelDetails | null>(null)
  const [loadingDetails, setLoadingDetails] = useState(false)

  const fetchModelDetails = async () => {
    setLoadingDetails(true)
    try {
      const response = await fetch('/ui/api/model-details', {
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

  useEffect(() => {
    if (isExpanded && !details && !loadingDetails) {
      fetchModelDetails()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isExpanded, details, loadingDetails])

  const formatSize = (bytes: number) => {
    if (!bytes) return '0 B'
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(1024))
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i]
  }

  return (
    <tr className="hover:bg-gray-50">
      <td colSpan={3} className="px-4 py-2 border-b border-gray-100">
        <div className="w-full">
          <div className="flex items-center justify-between py-1.5 gap-4">
            <div className="flex items-center gap-2 flex-1">
              <button
                className="bg-transparent border-none cursor-pointer p-1 text-sm text-gray-600 transition-colors hover:text-primary"
                onClick={onToggleExpand}
              >
                <span>{isExpanded ? '▼' : '▶'}</span>
              </button>
              <div>
                <div className="font-medium text-gray-900 text-sm flex items-center gap-1">
                  {model.name}
                  {model.supports_vision && <span title="Supports vision/images">👁️</span>}
                  {model.supports_tools && <span title="Supports tools/functions">⛏️</span>}
                </div>
                <div className="text-gray-600 text-xs">{formatSize(model.size)}</div>
              </div>
            </div>
            <div className="flex-shrink-0">
              {isLoaded ? (
                <>
                  <span className="inline-block bg-success text-white px-3 py-1.5 rounded-md text-xs font-medium">
                    Loaded on {loadedOn.join(', ')}
                  </span>
                </>
              ) : (
                <span className="inline-block bg-gray-100 text-gray-700 px-3 py-1.5 rounded-md text-xs font-medium">Available</span>
              )}
            </div>
            <div className="flex-shrink-0 flex items-center gap-2">
              {isLoaded ? (
                <button
                  className="px-3 py-1.5 rounded-md border-none text-xs font-medium cursor-pointer transition-all bg-danger text-white hover:brightness-90 disabled:opacity-50 disabled:cursor-not-allowed"
                  onClick={onUnload}
                >
                  Unload
                </button>
              ) : (
                <button
                  className="px-3 py-1.5 rounded-md border-none text-xs font-medium cursor-pointer transition-all bg-primary text-white hover:bg-primary-dark disabled:opacity-50 disabled:cursor-not-allowed"
                  onClick={onLoad}
                >
                  Load
                </button>
              )}
              <button
                className="px-3 py-1.5 rounded-md border-none text-xs font-medium cursor-pointer transition-all bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={onDelete}
                title={`Delete ${model.name}`}
              >
                Delete
              </button>
            </div>
          </div>

          {isExpanded && (
            <div className="border-t border-gray-200 mt-1 pt-3 pb-3">
              {loadingDetails ? (
                <div className="p-4 text-center text-gray-500">Loading model details...</div>
              ) : details ? (
                <div className="px-6">
                  {details.model_info ? (
                    <div className="mb-6">
                      <h4 className="text-sm font-semibold text-gray-700 mb-2">Model Information</h4>
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                        {details.details?.format && (
                          <div className="text-sm">
                            <span className="font-medium text-gray-600 mr-2">Format:</span> {details.details.format}
                          </div>
                        )}
                        {details.details?.family && (
                          <div className="text-sm">
                            <span className="font-medium text-gray-600 mr-2">Family:</span> {details.details.family}
                          </div>
                        )}
                        {details.details?.parameter_size && (
                          <div className="text-sm">
                            <span className="font-medium text-gray-600 mr-2">Parameters:</span> {details.details.parameter_size}
                          </div>
                        )}
                        {details.details?.quantization_level && (
                          <div className="text-sm">
                            <span className="font-medium text-gray-600 mr-2">Quantization:</span> {details.details.quantization_level}
                          </div>
                        )}
                      </div>
                    </div>
                  ) : null}

                  {details.template ? (
                    <div className="mb-6">
                      <h4 className="text-sm font-semibold text-gray-700 mb-2">Template</h4>
                      <pre className="bg-gray-50 p-4 rounded text-xs leading-relaxed overflow-x-auto whitespace-pre-wrap break-words max-w-full max-h-[200px] overflow-y-auto">{details.template}</pre>
                    </div>
                  ) : null}

                  {details.system ? (
                    <div className="mb-6 max-w-full">
                      <h4 className="text-sm font-semibold text-gray-700 mb-2">System Prompt</h4>
                      <pre className="bg-gray-50 p-4 rounded text-xs leading-relaxed overflow-x-auto whitespace-pre-wrap break-words max-w-full max-h-[200px] overflow-y-auto">{details.system}</pre>
                    </div>
                  ) : null}

                  {details.parameters ? (
                    <div className="mb-0">
                      <h4 className="text-sm font-semibold text-gray-700 mb-2">Parameters</h4>
                      <pre className="bg-gray-50 p-4 rounded text-xs leading-relaxed overflow-x-auto whitespace-pre-wrap break-words max-w-full max-h-[200px] overflow-y-auto">{
                        typeof details.parameters === 'string'
                          ? details.parameters
                          : JSON.stringify(details.parameters, null, 2)
                      }</pre>
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="p-4 text-center text-danger">Failed to load model details</div>
              )}
            </div>
          )}
        </div>
      </td>
    </tr>
  )
}