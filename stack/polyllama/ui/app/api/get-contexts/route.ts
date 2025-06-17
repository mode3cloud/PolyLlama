import { NextRequest } from 'next/server'
import { proxyToRouter } from '../proxy-utils'

export async function GET(request: NextRequest) {
  return proxyToRouter('/api/polyllama/get-contexts', { request })
}