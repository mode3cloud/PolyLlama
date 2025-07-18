import { NextRequest, NextResponse } from 'next/server'
import { verifyAuth } from '../../../../auth-utils'

const LLM_PROXY_URL = process.env.LLM_PROXY_URL || 'http://llm-proxy:11435'

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  try {
    await verifyAuth(request)
    
    const { sessionId } = await params
    
    const response = await fetch(`${LLM_PROXY_URL}/api/sessions/${sessionId}/tool-selection`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    })
    
    if (!response.ok) {
      const error = await response.text()
      return NextResponse.json(
        { error: `Failed to get tool selection: ${error}` },
        { status: response.status }
      )
    }
    
    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error getting session tool selection:', error)
    return NextResponse.json(
      { error: 'Failed to get tool selection' },
      { status: 500 }
    )
  }
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  try {
    await verifyAuth(request)
    
    const { sessionId } = await params
    const body = await request.json()
    
    const response = await fetch(`${LLM_PROXY_URL}/api/sessions/${sessionId}/tool-selection`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body)
    })
    
    if (!response.ok) {
      const error = await response.text()
      return NextResponse.json(
        { error: `Failed to update tool selection: ${error}` },
        { status: response.status }
      )
    }
    
    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error updating session tool selection:', error)
    return NextResponse.json(
      { error: 'Failed to update tool selection' },
      { status: 500 }
    )
  }
}