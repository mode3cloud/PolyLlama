import { NextRequest, NextResponse } from 'next/server'
import { verifyAuth } from '../../../auth-utils'

export async function GET(
  request: NextRequest,
  { params }: { params: { sessionId: string } }
) {
  // Verify authentication
  const auth = verifyAuth(request)
  if (!auth.valid) {
    return NextResponse.json(
      { error: 'Authentication required' },
      { status: 401 }
    )
  }

  try {
    const { sessionId } = params

    // Get session messages from LLM proxy
    const response = await fetch(`http://llm-proxy:11435/api/sessions/${sessionId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      const error = await response.text()
      return NextResponse.json(
        { error: `Failed to fetch session: ${error}` },
        { status: response.status }
      )
    }

    const session = await response.json()
    return NextResponse.json(session)
  } catch (error) {
    console.error('Error fetching session:', error)
    return NextResponse.json(
      { error: 'Failed to fetch session' },
      { status: 500 }
    )
  }
}