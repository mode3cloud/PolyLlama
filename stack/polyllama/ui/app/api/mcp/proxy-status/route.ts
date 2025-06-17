import { NextRequest, NextResponse } from 'next/server'
import { proxyToLLM } from '../../proxy-to-llm'

// This endpoint checks the proxy's MCP integration status
export async function GET(request: NextRequest) {
  // Using a shorter timeout for health check
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 5000)
  
  try {
    const response = await proxyToLLM('/api/mcp/status', { 
      request,
      headers: {
        'signal': controller.signal as any
      }
    })
    clearTimeout(timeoutId)
    
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
    clearTimeout(timeoutId)
    console.error('Error checking proxy MCP status:', error)
    return NextResponse.json(
      { available: false, error: 'Unable to connect to MCP service' },
      { status: 503 }
    )
  }
}