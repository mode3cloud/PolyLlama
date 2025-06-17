import { NextRequest, NextResponse } from 'next/server'

export async function proxyToRouter(
  endpoint: string,
  options: {
    method?: string
    body?: any
    headers?: Record<string, string>
  } = {}
) {
  const url = `http://router:11434${endpoint}`
  
  const headers: Record<string, string> = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    ...options.headers,
  }
  
  // Add API key if configured
  if (process.env.POLYLLAMA_API_KEY) {
    headers['api-key'] = process.env.POLYLLAMA_API_KEY
  }
  
  try {
    const response = await fetch(url, {
      method: options.method || 'GET',
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    })
    
    const data = await response.json()
    
    if (!response.ok) {
      return NextResponse.json(data, { status: response.status })
    }
    
    return NextResponse.json(data)
  } catch (error) {
    console.error(`Error proxying to ${endpoint}:`, error)
    return NextResponse.json(
      { error: `Failed to proxy request to ${endpoint}` },
      { status: 500 }
    )
  }
}