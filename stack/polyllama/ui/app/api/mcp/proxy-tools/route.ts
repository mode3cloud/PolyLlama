import { NextRequest } from 'next/server'
import { proxyToLLM } from '../../proxy-to-llm'

export async function GET(request: NextRequest) {
  return proxyToLLM('/api/mcp/tools/formatted', { request })
}