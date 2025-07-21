import { NextRequest, NextResponse } from 'next/server'
import { verifyAuth } from '../auth-utils'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    
    // Validate required fields
    if (!body.name || !body.from) {
      return Response.json(
        { error: 'Name and from are required' },
        { status: 400 }
      )
    }

    // Verify authentication
    const auth = verifyAuth(request)
    if (!auth.valid) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      )
    }

    // Proxy to Ollama's /api/create endpoint with streaming support
    const url = `http://router:11434/api/create`
    
    const headers: Record<string, string> = {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
    }
    
    // Add API key if configured
    if (process.env.POLYLLAMA_API_KEY) {
      headers['Authorization'] = `Bearer ${process.env.POLYLLAMA_API_KEY}`
    }
    
    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    })
    
    if (!response.ok) {
      const errorText = await response.text()
      console.error(`Error from router: ${response.status} - ${errorText}`)
      return NextResponse.json(
        { error: `Server error: ${response.statusText}` },
        { status: response.status }
      )
    }

    // Return the streaming response directly
    return new NextResponse(response.body, {
      status: response.status,
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      },
    })
  } catch (error) {
    console.error('Error creating model:', error)
    return Response.json(
      { error: 'Failed to create model' },
      { status: 500 }
    )
  }
}