import { NextRequest, NextResponse } from 'next/server'

const LLM_PROXY_URL = process.env.LLM_PROXY_URL || 'http://llm-proxy:11435'

export async function GET(request: NextRequest) {
  try {
    const response = await fetch(`${LLM_PROXY_URL}/api/models`, {
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      throw new Error(`LLM proxy responded with status: ${response.status}`)
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error fetching models from LLM proxy:', error)
    return NextResponse.json(
      { error: 'Failed to fetch models', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    )
  }
}