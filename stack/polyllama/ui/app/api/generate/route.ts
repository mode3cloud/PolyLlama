import { NextRequest } from 'next/server'
import { proxyToRouter } from '../proxy-utils'

export async function POST(request: NextRequest) {
  const body = await request.json()
  // This is a standard Ollama endpoint
  return proxyToRouter('/api/generate', {
    method: 'POST',
    body
  })
}