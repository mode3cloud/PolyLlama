import { NextResponse } from 'next/server'

export async function GET() {
  try {
    // Check agent controller status
    const response = await fetch('http://agent-controller:11436/agent/status', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    })

    if (!response.ok) {
      return NextResponse.json(
        { 
          status: 'error', 
          message: 'Agent controller unavailable',
          agentController: false 
        },
        { status: 503 }
      )
    }

    const agentStatus = await response.json()
    
    return NextResponse.json({
      status: 'healthy',
      agentController: true,
      ...agentStatus
    })
  } catch (error) {
    console.error('Agent status check error:', error)
    return NextResponse.json(
      { 
        status: 'error', 
        message: 'Failed to check agent status',
        agentController: false 
      },
      { status: 500 }
    )
  }
}