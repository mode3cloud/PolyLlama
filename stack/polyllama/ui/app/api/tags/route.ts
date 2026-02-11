import { NextRequest, NextResponse } from 'next/server'
import { verifyAuth } from '../auth-utils'
import { getModelCapabilities } from '../../utils/modelCapabilities'

export async function GET(request: NextRequest) {
  try {
    // Verify authentication
    const auth = verifyAuth(request)
    if (!auth.valid) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      )
    }

    // Call the Ollama /api/tags endpoint
    const url = `http://router:11434/api/tags`
    
    const headers: Record<string, string> = {
      'Accept': 'application/json',
    }

    // Add API key if configured
    if (process.env.POLYLLAMA_API_KEY) {
      headers['api-key'] = process.env.POLYLLAMA_API_KEY
    }
    
    const response = await fetch(url, {
      method: 'GET',
      headers,
    })
    
    if (!response.ok) {
      const errorText = await response.text()
      console.error(`Error from router: ${response.status} - ${errorText}`)
      return NextResponse.json(
        { error: `Server error: ${response.statusText}` },
        { status: response.status }
      )
    }

    const data = await response.json()
    
    // Enrich models with capability information
    if (data.models && Array.isArray(data.models)) {
      data.models = data.models.map((model: any) => {
        const capabilities = getModelCapabilities(model.name)
        return {
          ...model,
          supports_vision: capabilities.supports_vision,
          supports_tools: capabilities.supports_tools
        }
      })
    }
    
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error fetching models:', error)
    return NextResponse.json(
      { error: 'Failed to fetch models' },
      { status: 500 }
    )
  }
}