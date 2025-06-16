import { NextRequest, NextResponse } from 'next/server'

const LLM_PROXY_URL = process.env.LLM_PROXY_URL || 'http://llm-proxy:11435'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    
    // If MCP tools are enabled, fetch tools from llm-proxy
    if (body.enableMCPTools && !body.tools) {
      console.log('[MCP] Tools requested, fetching from llm-proxy...')
      
      try {
        const toolsResponse = await fetch(`${LLM_PROXY_URL}/api/mcp/tools/formatted`)
        if (toolsResponse.ok) {
          const toolsData = await toolsResponse.json()
          if (toolsData.tools && toolsData.tools.length > 0) {
            body.tools = toolsData.tools
            console.log(`[MCP] Injected ${toolsData.tools.length} tools into request`)
          } else {
            console.log('[MCP] No tools available from llm-proxy')
          }
        } else {
          console.warn('[MCP] Failed to fetch tools from llm-proxy:', toolsResponse.status)
        }
      } catch (error) {
        console.warn('[MCP] Error fetching tools from llm-proxy:', error)
        // Continue without MCP tools
      }
    }
    
    const response = await fetch(`${LLM_PROXY_URL}/api/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      throw new Error(`LLM proxy responded with status: ${response.status}`)
    }

    // For streaming responses, pass through the stream
    if (body.stream) {
      const stream = response.body
      if (!stream) {
        throw new Error('No response stream available')
      }

      // Return a streaming response
      return new NextResponse(stream, {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      })
    }

    // For non-streaming responses
    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error proxying to LLM proxy:', error)
    return NextResponse.json(
      { error: 'Failed to process request', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    )
  }
}