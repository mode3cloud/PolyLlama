import { NextRequest, NextResponse } from 'next/server'

const LLM_PROXY_URL = process.env.LLM_PROXY_URL || 'http://llm-proxy:11435'

export async function GET() {
  try {
    const response = await fetch(`${LLM_PROXY_URL}/api/mcp/tools`)
    
    if (!response.ok) {
      throw new Error(`LLM proxy responded with status: ${response.status}`)
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error proxying MCP tools request:', error)
    return NextResponse.json(
      { 
        error: 'Failed to fetch MCP tools', 
        details: error instanceof Error ? error.message : 'Unknown error' 
      },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    
    const response = await fetch(`${LLM_PROXY_URL}/api/mcp/tools/execute`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`LLM proxy responded with status: ${response.status}, message: ${errorText}`)
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error proxying MCP tool execution:', error)
    return NextResponse.json(
      { 
        error: 'Failed to execute MCP tool', 
        details: error instanceof Error ? error.message : 'Unknown error' 
      },
      { status: 500 }
    )
  }
}