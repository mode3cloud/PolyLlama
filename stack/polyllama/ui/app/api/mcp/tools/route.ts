import { NextRequest, NextResponse } from 'next/server'

// These endpoints now redirect to the proxy tools endpoints
export async function GET() {
  return NextResponse.redirect(new URL('/ui/api/mcp/proxy-tools', process.env.NEXT_PUBLIC_URL || 'http://localhost:11434'))
}

export async function POST(request: NextRequest) {
  // Redirect POST requests to the proxy endpoint
  const body = await request.json()
  
  const response = await fetch(new URL('/ui/api/mcp/proxy-tools', process.env.NEXT_PUBLIC_URL || 'http://localhost:11434').toString(), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  
  const data = await response.json()
  return NextResponse.json(data, { status: response.status })
}