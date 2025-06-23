import { NextRequest, NextResponse } from 'next/server'
import { verifyAuth } from './auth-utils'

export async function proxyToRouter(
  endpoint: string,
  options: {
    method?: string
    body?: unknown
    headers?: Record<string, string>
    request?: NextRequest
  } = {}
) {
  // Verify authentication if request is provided
  if (options.request) {
    const auth = verifyAuth(options.request)
    if (!auth.valid) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      )
    }
  }
  const url = `http://router:11434${endpoint}`
  
  const headers: Record<string, string> = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    ...options.headers,
  }
  
  // Add API key if configured
  if (process.env.POLYLLAMA_API_KEY) {
    headers['Authorization'] = `Bearer ${process.env.POLYLLAMA_API_KEY}`
  }
  
  try {
    const response = await fetch(url, {
      method: options.method || 'GET',
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    })
    
    // Check if response is JSON
    const contentType = response.headers.get('content-type')
    if (contentType && contentType.includes('application/json')) {
      const data = await response.json()
      
      if (!response.ok) {
        return NextResponse.json(data, { status: response.status })
      }
      
      return NextResponse.json(data)
    } else {
      // Non-JSON response (likely HTML error page)
      const text = await response.text()
      console.error(`Non-JSON response from ${endpoint}: ${text}`)
      
      return NextResponse.json(
        { error: `Invalid response from server: ${response.statusText}` },
        { status: response.status }
      )
    }
  } catch (error) {
    console.error(`Error proxying to ${endpoint}:`, error)
    return NextResponse.json(
      { error: `Failed to proxy request to ${endpoint}` },
      { status: 500 }
    )
  }
}