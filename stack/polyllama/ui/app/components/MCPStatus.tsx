'use client'

import { useState, useEffect } from 'react'

interface Tool {
  name: string
  description?: string
  inputSchema?: any
}

interface MCPStatusResponse {
  status: string
  message?: string
  servers?: Record<string, {
    connected?: boolean
    command?: string
    args?: string[]
    toolCount?: number
    lastError?: string | null
    lastHealthCheck?: number | null
    tools?: Tool[]
  }>
  total_tools?: number
  cache_tools?: number
  connected_tools?: number
}

export default function MCPStatus() {
  const [mcpStatus, setMCPStatus] = useState<MCPStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [isExpanded, setIsExpanded] = useState(false)
  const [expandedServers, setExpandedServers] = useState<Set<string>>(new Set())

  useEffect(() => {
    fetchMCPStatus()
  }, [])

  useEffect(() => {
    // Refetch with tools when expanded state changes
    if (isExpanded) {
      fetchMCPStatus()
    }
    
    // Refresh every 30 seconds when expanded
    const interval = setInterval(() => {
      if (isExpanded) {
        fetchMCPStatus()
      }
    }, 30000)
    
    return () => clearInterval(interval)
  }, [isExpanded])

  const fetchMCPStatus = async () => {
    try {
      // Include tools when expanded
      const url = isExpanded ? '/ui/api/mcp/proxy-status?includeTools=true' : '/ui/api/mcp/proxy-status'
      const response = await fetch(url)
      const data = await response.json()
      setMCPStatus(data)
    } catch (error) {
      console.error('Failed to fetch MCP status:', error)
      setMCPStatus({
        status: 'error',
        message: 'Failed to fetch MCP status'
      })
    } finally {
      setLoading(false)
    }
  }

  const toggleServerExpanded = (serverName: string) => {
    setExpandedServers(prev => {
      const newSet = new Set(prev)
      if (newSet.has(serverName)) {
        newSet.delete(serverName)
      } else {
        newSet.add(serverName)
      }
      return newSet
    })
  }

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg p-4 mb-4">
        <div className="text-gray-400">Loading MCP status...</div>
      </div>
    )
  }

  if (!mcpStatus || mcpStatus.status === 'not_configured') {
    return null
  }

  const statusColor = mcpStatus.status === 'configured' ? 'text-green-400' : 'text-yellow-400'
  const toolsCount = mcpStatus.total_tools || 0
  const serversData = mcpStatus.servers || {}
  
  // Convert servers object to array format
  const servers = Object.entries(serversData).map(([name, data]) => {
    const serverInfo = data as {
      connected?: boolean
      command?: string
      args?: string[]
      toolCount?: number
      lastError?: string | null
      lastHealthCheck?: number | null
      tools?: Tool[]
    }
    return {
      name,
      connected: serverInfo.connected || false,
      command: serverInfo.command || '',
      args: serverInfo.args || [],
      toolCount: serverInfo.toolCount || 0,
      lastError: serverInfo.lastError,
      lastHealthCheck: serverInfo.lastHealthCheck,
      tools: serverInfo.tools || []
    }
  })

  return (
    <div className="bg-gray-800 rounded-lg p-4 mb-4">
      <div className="flex items-center justify-between cursor-pointer" onClick={() => setIsExpanded(!isExpanded)}>
        <div className="flex items-center gap-2">
          <h3 className="text-white font-semibold">MCP Tools</h3>
          <span className={`text-sm ${statusColor}`}>
            {mcpStatus.status === 'configured' ? `${toolsCount} tools available` : 'Not configured'}
          </span>
        </div>
        <svg className={`w-5 h-5 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>

      {isExpanded && servers.length > 0 && (
        <div className="mt-4 space-y-2">
          {servers.map((server) => {
            const isServerExpanded = expandedServers.has(server.name)
            return (
              <div key={server.name} className="bg-gray-700 rounded p-3">
                <div 
                  className="flex items-center justify-between cursor-pointer"
                  onClick={() => toggleServerExpanded(server.name)}
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <div className="text-white font-medium">{server.name}</div>
                      {server.connected && server.toolCount > 0 && (
                        <span className="text-gray-400 text-sm">({server.toolCount} tools)</span>
                      )}
                    </div>
                    <div className="text-gray-400 text-sm mt-1">
                      {server.command} {server.args.join(' ')}
                    </div>
                    {server.lastError && (
                      <div className="text-red-400 text-xs mt-1">
                        Error: {server.lastError}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-1 rounded ${
                      server.connected ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'
                    }`}>
                      {server.connected ? 'Connected' : 'Disconnected'}
                    </span>
                    {server.connected && server.toolCount > 0 && (
                      <svg className={`w-4 h-4 text-gray-400 transition-transform ${isServerExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    )}
                  </div>
                </div>
                
                {/* Tool list */}
                {isServerExpanded && server.tools.length > 0 && (
                  <div className="mt-3 space-y-1 border-t border-gray-600 pt-3">
                    <div className="text-gray-400 text-xs font-semibold mb-2">Available Tools:</div>
                    <div className="max-h-60 overflow-y-auto space-y-1">
                      {server.tools.map((tool, index) => (
                        <div key={`${tool.name}-${index}`} className="bg-gray-800 rounded p-2">
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="text-white text-sm font-mono">{tool.name}</div>
                              {tool.description && (
                                <div className="text-gray-400 text-xs mt-1">{tool.description}</div>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
          
          {/* Debug info */}
          {mcpStatus.cache_tools !== undefined && (
            <div className="text-xs text-gray-500 mt-2">
              Debug: Connected tools: {mcpStatus.connected_tools || 0}, 
              Cached tools: {mcpStatus.cache_tools || 0}
            </div>
          )}
        </div>
      )}
    </div>
  )
}