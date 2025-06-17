import { NextRequest } from 'next/server'
import { proxyToRouter } from '../proxy-utils'

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const query = searchParams.get('q') || ''
  
  return proxyToRouter(`/api/polyllama/search-models?q=${encodeURIComponent(query)}`, { request })
}