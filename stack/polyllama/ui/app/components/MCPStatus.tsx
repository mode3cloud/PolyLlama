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

export interface ToolSelection {
  [serverName: string]: {
    [toolName: string]: boolean
  }
}

interface MCPStatusProps {
  toolSelection?: ToolSelection
  onToolSelectionChange?: (selection: ToolSelection) => void
  maxTools?: number
}

export default function MCPStatus({ 
  toolSelection, 
  onToolSelectionChange, 
  maxTools = 128 
}: MCPStatusProps) {
  const [mcpStatus, setMCPStatus] = useState<MCPStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [isExpanded, setIsExpanded] = useState(false)
  const [expandedServers, setExpandedServers] = useState<Set<string>>(new Set())
  const [showToolSelection, setShowToolSelection] = useState(false)

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

  // Calculate selected tools count
  const getSelectedToolsCount = (): number => {
    if (!toolSelection || !mcpStatus?.servers) return 0
    return Object.entries(toolSelection).reduce((total, [serverName, tools]) => {
      return total + Object.values(tools).filter(Boolean).length
    }, 0)
  }

  // Toggle tool selection
  const toggleToolSelection = (serverName: string, toolName: string) => {
    if (!onToolSelectionChange || !toolSelection) return
    
    const newSelection = {
      ...toolSelection,
      [serverName]: {
        ...toolSelection[serverName],
        [toolName]: !toolSelection[serverName]?.[toolName]
      }
    }
    onToolSelectionChange(newSelection)
  }

  // Toggle all tools for a server
  const toggleServerTools = (serverName: string, enable: boolean) => {
    if (!onToolSelectionChange || !toolSelection || !mcpStatus?.servers) return
    
    const serverData = mcpStatus.servers[serverName]
    if (!serverData?.tools) return
    
    const newSelection = {
      ...toolSelection,
      [serverName]: serverData.tools.reduce((acc, tool) => {
        acc[tool.name] = enable
        return acc
      }, {} as { [toolName: string]: boolean })
    }
    onToolSelectionChange(newSelection)
  }

  // Smart selection: enable popular/essential tools up to maxTools limit
  const enableSmartSelection = () => {
    if (!onToolSelectionChange || !mcpStatus?.servers) return
    
    const allTools: Array<{ serverName: string; toolName: string; tool: Tool }> = []
    
    // Collect all tools
    Object.entries(mcpStatus.servers).forEach(([serverName, serverData]) => {
      if (serverData.tools) {
        serverData.tools.forEach(tool => {
          allTools.push({ serverName, toolName: tool.name, tool })
        })
      }
    })
    
    // Sort by priority (basic heuristic - prioritize shorter names as they're likely more common)
    allTools.sort((a, b) => {
      const aScore = getToolPriority(a.tool)
      const bScore = getToolPriority(b.tool)
      return bScore - aScore
    })
    
    // Select top tools up to maxTools
    const selectedTools = allTools.slice(0, maxTools)
    
    const newSelection: ToolSelection = {}
    selectedTools.forEach(({ serverName, toolName }) => {
      if (!newSelection[serverName]) {
        newSelection[serverName] = {}
      }
      newSelection[serverName][toolName] = true
    })
    
    onToolSelectionChange(newSelection)
  }

  // Tool priority scoring (higher is better)
  const getToolPriority = (tool: Tool): number => {
    let score = 0
    
    // Shorter names often indicate more common tools
    score += Math.max(0, 50 - tool.name.length)
    
    // Prioritize certain keywords
    const highPriorityWords = ['search', 'get', 'list', 'read', 'fetch', 'query', 'find']
    const mediumPriorityWords = ['create', 'update', 'delete', 'write', 'execute', 'run']
    
    const name = tool.name.toLowerCase()
    if (highPriorityWords.some(word => name.includes(word))) score += 20
    if (mediumPriorityWords.some(word => name.includes(word))) score += 10
    
    return score
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
  const selectedToolsCount = getSelectedToolsCount()
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
            {mcpStatus.status === 'configured' ? (
              toolSelection && onToolSelectionChange ? (
                <span className={selectedToolsCount > maxTools ? 'text-red-400' : 'text-green-400'}>
                  {selectedToolsCount}/{maxTools} tools selected
                </span>
              ) : (
                `${toolsCount} tools available`
              )
            ) : 'Not configured'}
          </span>
          {toolSelection && onToolSelectionChange && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                setShowToolSelection(!showToolSelection)
              }}
              className="text-xs bg-blue-600 hover:bg-blue-700 text-white px-2 py-1 rounded"
            >
              {showToolSelection ? 'Hide Selection' : 'Select Tools'}
            </button>
          )}
        </div>
        <svg className={`w-5 h-5 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>

      {/* Tool Selection UI */}
      {showToolSelection && toolSelection && onToolSelectionChange && (
        <div className="mt-4 p-4 bg-gray-700 rounded-lg">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-white font-medium">Tool Selection</h4>
            <div className="flex gap-2">
              <button
                onClick={enableSmartSelection}
                className="text-xs bg-green-600 hover:bg-green-700 text-white px-2 py-1 rounded"
              >
                Smart Select ({maxTools})
              </button>
              <button
                onClick={() => onToolSelectionChange({})}
                className="text-xs bg-red-600 hover:bg-red-700 text-white px-2 py-1 rounded"
              >
                Clear All
              </button>
            </div>
          </div>
          
          {selectedToolsCount > maxTools && (
            <div className="bg-red-900 text-red-200 text-xs p-2 rounded mb-3">
              Warning: {selectedToolsCount} tools selected exceeds OpenAI limit of {maxTools}. 
              Some tools may be ignored.
            </div>
          )}
          
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {servers.map((server) => (
              <div key={server.name} className="bg-gray-800 rounded p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-white font-medium">{server.name}</span>
                    <span className="text-gray-400 text-sm">
                      ({server.tools.filter(tool => toolSelection[server.name]?.[tool.name]).length}/{server.tools.length})
                    </span>
                  </div>
                  <div className="flex gap-1">
                    <button
                      onClick={() => toggleServerTools(server.name, true)}
                      className="text-xs bg-green-600 hover:bg-green-700 text-white px-2 py-1 rounded"
                    >
                      All
                    </button>
                    <button
                      onClick={() => toggleServerTools(server.name, false)}
                      className="text-xs bg-red-600 hover:bg-red-700 text-white px-2 py-1 rounded"
                    >
                      None
                    </button>
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-1 max-h-32 overflow-y-auto">
                  {server.tools.map((tool) => (
                    <label key={tool.name} className="flex items-center gap-2 text-sm p-1 hover:bg-gray-700 rounded cursor-pointer">
                      <input
                        type="checkbox"
                        checked={toolSelection[server.name]?.[tool.name] || false}
                        onChange={() => toggleToolSelection(server.name, tool.name)}
                        className="w-3 h-3 text-blue-600 rounded focus:ring-blue-500"
                      />
                      <span className="text-white font-mono text-xs truncate" title={tool.name}>
                        {tool.name}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

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