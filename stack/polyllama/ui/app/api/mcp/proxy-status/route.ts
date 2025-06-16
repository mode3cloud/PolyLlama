import { NextRequest, NextResponse } from 'next/server'

const LLM_PROXY_URL = process.env.LLM_PROXY_URL || 'http://llm-proxy:11435'

export async function GET() {
  try {
    const response = await fetch(`${LLM_PROXY_URL}/api/mcp/status`)
    
    if (!response.ok) {
      throw new Error(`LLM proxy responded with status: ${response.status}`)
    }

    const data = await response.json()
    
    // Transform the response to match the UI's expected format
    const servers = data.servers || {}
    const serverDetails = Object.entries(servers).map(([name, info]: [string, any]) => ({
      name,
      command: info.command,
      args: info.args || [],
      hasEnvVars: false, // We don't expose env vars from the proxy
      status: info.connected ? 'connected' : 'configured'
    }))

    return NextResponse.json({
      status: data.status,
      message: `${serverDetails.length} MCP servers (${data.total_tools || 0} tools)`,
      servers: serverDetails
    })
  } catch (error) {
    console.error('Error proxying MCP status request:', error)
    return NextResponse.json(
      { 
        status: 'error',
        message: 'Failed to fetch MCP status', 
        servers: [],
        error: error instanceof Error ? error.message : 'Unknown error' 
      },
      { status: 500 }
    )
  }
}