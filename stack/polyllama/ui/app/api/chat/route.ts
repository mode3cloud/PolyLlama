import { NextRequest, NextResponse } from 'next/server'
import { verifyAuth } from '../auth-utils'

export async function POST(request: NextRequest) {
  // Verify authentication
  const auth = verifyAuth(request)
  if (!auth.valid) {
    return NextResponse.json(
      { error: 'Authentication required' },
      { status: 401 }
    )
  }

  try {
    const body = await request.json()
    
    // Add API key if configured for Ollama models
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    
    if (process.env.POLYLLAMA_API_KEY && body.model?.startsWith('ollama/')) {
      headers['Authorization'] = `Bearer ${process.env.POLYLLAMA_API_KEY}`
    }
    
    // Proxy to LLM proxy service
    const response = await fetch('http://llm-proxy:11435/api/chat/completions', {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    })

    // Handle streaming responses
    if (body.stream && response.ok) {
      const stream = response.body
      if (!stream) {
        throw new Error('No response body')
      }

      // Return the stream directly
      return new NextResponse(stream, {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      })
    }

    // Handle non-streaming responses
    if (!response.ok) {
      const error = await response.text()
      return NextResponse.json(
        { error: `LLM proxy error: ${error}` },
        { status: response.status }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error proxying to LLM proxy:', error)
    return NextResponse.json(
      { error: 'Failed to process chat request' },
      { status: 500 }
    )
  }
}