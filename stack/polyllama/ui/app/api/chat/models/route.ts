import { NextRequest, NextResponse } from 'next/server'
import { verifyAuth } from '../../auth-utils'

export async function GET(request: NextRequest) {
  // Verify authentication
  const auth = verifyAuth(request)
  if (!auth.valid) {
    return NextResponse.json(
      { error: 'Authentication required' },
      { status: 401 }
    )
  }

  try {
    // Proxy to LLM proxy service
    const response = await fetch('http://llm-proxy:11435/api/models', {
      headers: {
        'Accept': 'application/json',
      },
    })

    if (!response.ok) {
      const error = await response.text()
      return NextResponse.json(
        { error: `Failed to fetch models: ${error}` },
        { status: response.status }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error fetching models from LLM proxy:', error)
    return NextResponse.json(
      { error: 'Failed to fetch models' },
      { status: 500 }
    )
  }
}