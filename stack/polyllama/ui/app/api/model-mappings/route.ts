import { proxyToRouter } from '../proxy-utils'

export async function GET() {
  return proxyToRouter('/api/polyllama/model-mappings')
}