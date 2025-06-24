'use client'

import { useState, useEffect } from 'react'

interface MCPStatusResponse {
  status: string
  message?: string
  servers?: Record<string, {
    connected?: boolean
    command?: string
    args?: string[]
  }>
  total_tools?: number
}

export default function MCPStatus() {
  const [mcpStatus, setMCPStatus] = useState<MCPStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [isExpanded, setIsExpanded] = useState(false)

  useEffect(() => {
    fetchMCPStatus()
  }, [])

  const fetchMCPStatus = async () => {
    try {
      // Call llm-proxy MCP endpoint
      const response = await fetch('/ui/api/mcp/proxy-status')
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
    }
    return {
      name,
      connected: serverInfo.connected || false,
      command: serverInfo.command || '',
      args: serverInfo.args || []
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
          {servers.map((server) => (
            <div key={server.name} className="bg-gray-700 rounded p-3">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-white font-medium">{server.name}</div>
                  <div className="text-gray-400 text-sm mt-1">
                    {server.command} {server.args.join(' ')}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-1 rounded ${
                    server.connected ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'
                  }`}>
                    {server.connected ? 'Connected' : 'Disconnected'}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}