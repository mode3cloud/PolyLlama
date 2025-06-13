import { NextRequest, NextResponse } from 'next/server'

const LLM_PROXY_URL = process.env.LLM_PROXY_URL || 'http://llm-proxy:11435'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    
    const response = await fetch(`${LLM_PROXY_URL}/api/embeddings`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`LLM proxy responded with status: ${response.status}, message: ${errorText}`)
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error proxying embeddings request to LLM proxy:', error)
    return NextResponse.json(
      { 
        error: 'Failed to process embeddings request', 
        details: error instanceof Error ? error.message : 'Unknown error' 
      },
      { status: 500 }
    )
  }
}