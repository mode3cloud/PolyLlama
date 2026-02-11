import { NextRequest, NextResponse } from 'next/server'
import { verifyAuth } from '../../auth-utils'

// In-memory cache for models
interface CacheEntry {
  data: any
  timestamp: number
}

const modelsCache: Map<string, CacheEntry> = new Map()
const CACHE_TTL = 60 * 1000 // 60 seconds cache TTL

export async function GET(request: NextRequest) {
  // Verify authentication
  const auth = verifyAuth(request)
  if (!auth.valid) {
    return NextResponse.json(
      { error: 'Authentication required' },
      { status: 401 }
    )
  }

  // Check if we should force refresh
  const forceRefresh = request.nextUrl.searchParams.get('refresh') === 'true'
  const cacheKey = 'models-all'

  // Check cache first
  if (!forceRefresh) {
    const cached = modelsCache.get(cacheKey)
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      // Add cache headers
      return NextResponse.json(cached.data, {
        headers: {
          'X-Cache': 'HIT',
          'X-Cache-Age': String(Math.floor((Date.now() - cached.timestamp) / 1000)),
        }
      })
    }
  }

  try {
    // Proxy to LLM proxy service
    const headers: Record<string, string> = {
      'Accept': 'application/json',
    }

    // Add API key if configured
    if (process.env.POLYLLAMA_API_KEY) {
      headers['api-key'] = process.env.POLYLLAMA_API_KEY
    }

    const response = await fetch('http://router:11434/v1/models', {
      headers,
    })

    if (!response.ok) {
      const error = await response.text()
      return NextResponse.json(
        { error: `Failed to fetch models: ${error}` },
        { status: response.status }
      )
    }

    const data = await response.json()
    
    // Update cache
    modelsCache.set(cacheKey, {
      data,
      timestamp: Date.now()
    })

    // Clean up old cache entries
    if (modelsCache.size > 10) {
      const entries = Array.from(modelsCache.entries())
      entries.sort((a, b) => a[1].timestamp - b[1].timestamp)
      modelsCache.delete(entries[0][0])
    }

    return NextResponse.json(data, {
      headers: {
        'X-Cache': 'MISS',
        'Cache-Control': 'private, max-age=60',
      }
    })
  } catch (error) {
    console.error('Error fetching models from LLM proxy:', error)
    return NextResponse.json(
      { error: 'Failed to fetch models' },
      { status: 500 }
    )
  }
}