import { NextRequest } from 'next/server'
import { NextRequest } from 'next/server'
import { proxyToRouter } from '../proxy-utils'

export async function POST(request: NextRequest) {
  const body = await request.json(), { request })
  return proxyToRouter('/api/polyllama/model-details', {
    method: 'POST',
    body
  }), { request })
}