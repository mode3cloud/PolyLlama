import { NextRequest, NextResponse } from 'next/server'

// This endpoint now redirects to the proxy status endpoint
export async function GET() {
  return NextResponse.redirect(new URL('/ui/api/mcp/proxy-status', process.env.NEXT_PUBLIC_URL || 'http://localhost:11434'))
}