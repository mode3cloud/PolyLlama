import { NextRequest, NextResponse } from 'next/server'

const LLM_PROXY_URL = process.env.LLM_PROXY_URL || 'http://llm-proxy:11435'

export async function GET(request: NextRequest) {
  try {
    // Test connectivity to LLM proxy
    const response = await fetch(`${LLM_PROXY_URL}/health`)
    const health = await response.json()
    
    // Also test models endpoint
    const modelsResponse = await fetch(`${LLM_PROXY_URL}/api/models`)
    const models = await modelsResponse.json()
    
    return NextResponse.json({
      status: 'ok',
      llm_proxy_url: LLM_PROXY_URL,
      llm_proxy_health: health,
      models_count: models.models?.length || 0,
      endpoints: {
        models: '/ui/api/chat/models',
        completions: '/ui/api/chat/completions',
        test: '/ui/api/chat/test'
      }
    })
  } catch (error) {
    console.error('Test endpoint error:', error)
    return NextResponse.json(
      { 
        status: 'error',
        error: error instanceof Error ? error.message : 'Unknown error',
        llm_proxy_url: LLM_PROXY_URL
      },
      { status: 500 }
    )
  }
}