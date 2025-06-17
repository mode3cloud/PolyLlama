import { proxyToRouter } from '../proxy-utils'

export async function GET() {
  // This is a standard Ollama endpoint
  return proxyToRouter('/api/tags')
}