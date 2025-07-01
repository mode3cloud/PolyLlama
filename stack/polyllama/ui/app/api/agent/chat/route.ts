import { NextRequest, NextResponse } from 'next/server'

export async function POST(req: NextRequest) {
  try {
    const { userPrompt, sessionId, model } = await req.json()
    
    if (!userPrompt) {
      return NextResponse.json(
        { error: 'userPrompt is required' },
        { status: 400 }
      )
    }

    // Forward request to agent controller service
    const response = await fetch('http://agent-controller:11436/agent/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        userPrompt,
        sessionId,
        model
      })
    })

    if (!response.ok) {
      return NextResponse.json(
        { error: 'Agent controller error' },
        { status: response.status }
      )
    }

    // Stream the response from agent controller to client
    return new NextResponse(response.body, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      }
    })
  } catch (error) {
    console.error('Agent chat error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

export async function GET() {
  return NextResponse.json({
    message: 'Agent chat endpoint. Use POST to send messages.'
  })
}