import { NextRequest, NextResponse } from 'next/server'
import { verifyAuth } from '../../auth-utils'

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
    
    // Process tool selection if provided
    let processedBody = { ...body }
    if (body.tool_selection) {
      processedBody.tool_selection = body.tool_selection
    }
    
    // Proxy to LLM proxy service
    const response = await fetch('http://router:11434/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(processedBody),
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
      
      // Check for specific tool limit error
      if (error.includes('array too long') && error.includes('maximum length 128')) {
        return NextResponse.json(
          { 
            error: 'Too many tools selected. Please reduce your tool selection to 128 or fewer tools.',
            details: error,
            code: 'TOOL_LIMIT_EXCEEDED'
          },
          { status: 400 }
        )
      }
      
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
      { error: 'Failed to process chat completion' },
      { status: 500 }
    )
  }
}