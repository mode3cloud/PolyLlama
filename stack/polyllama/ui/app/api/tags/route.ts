import { NextRequest } from 'next/server'
import { proxyToRouter } from '../proxy-utils'

export async function GET(request: NextRequest) {
  // This is a standard Ollama endpoint
  return proxyToRouter('/api/tags'), { request })
}