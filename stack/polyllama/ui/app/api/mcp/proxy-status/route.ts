import { NextRequest, NextResponse } from 'next/server'
import { proxyToLLM } from '../../proxy-to-llm'

// This endpoint checks the proxy's MCP integration status
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const includeTools = searchParams.get('includeTools') === 'true'
  
  try {
    const url = includeTools ? '/api/mcp/status?include_tools=true' : '/api/mcp/status'
    const response = await proxyToLLM(url, { 
      request
    })
    
    // Extract the JSON data from the NextResponse
    const data = await response.json()
    
    if (response.status !== 200) {
      return NextResponse.json(
        { available: false, error: 'MCP service not responding' },
        { status: response.status }
      )
    }
    
    return NextResponse.json({
      available: true,
      ...data
    })
  } catch (error) {
    console.error('Error checking proxy MCP status:', error)
    return NextResponse.json(
      { available: false, error: 'Unable to connect to MCP service' },
      { status: 503 }
    )
  }
}