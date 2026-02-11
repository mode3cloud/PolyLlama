import { NextRequest, NextResponse } from 'next/server'
import { verifyAuth } from '../auth-utils'

export async function DELETE(request: NextRequest) {
  try {
    const body = await request.json()
    
    // Validate required fields
    if (!body.model) {
      return Response.json(
        { error: 'Model name is required' },
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

    // Proxy to Ollama's /api/delete endpoint
    const url = `http://router:11434/api/delete`
    
    const headers: Record<string, string> = {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
    }
    
    // Add API key if configured
    if (process.env.POLYLLAMA_API_KEY) {
      headers['api-key'] = process.env.POLYLLAMA_API_KEY
    }
    
    const response = await fetch(url, {
      method: 'DELETE',
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

    // Check if we have a response body
    const responseText = await response.text()
    
    if (responseText) {
      try {
        const data = JSON.parse(responseText)
        return NextResponse.json(data, { status: response.status })
      } catch (e) {
        // If it's not JSON, return as text
        return NextResponse.json({ message: responseText }, { status: response.status })
      }
    } else {
      // No response body, return success
      return NextResponse.json({ success: true }, { status: response.status })
    }
  } catch (error) {
    console.error('Error deleting model:', error)
    return Response.json(
      { error: 'Failed to delete model' },
      { status: 500 }
    )
  }
}