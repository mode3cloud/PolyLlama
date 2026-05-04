import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { verifyToken } from './app/lib/auth/jwt'

export function middleware(request: NextRequest) {
  // Skip auth check for auth endpoints themselves
  if (request.nextUrl.pathname.startsWith('/ui/api/auth/')) {
    return NextResponse.next()
  }

  // Skip auth check for public assets
  if (
    request.nextUrl.pathname.startsWith('/_next') ||
    request.nextUrl.pathname.startsWith('/favicon.ico')
  ) {
    return NextResponse.next()
  }

  // Development mode bypass - skip auth if SKIP_AUTH is set
  if (process.env.SKIP_AUTH === 'true') {
    // Add fake user info for development
    const requestHeaders = new Headers(request.headers)
    requestHeaders.set('x-user-email', 'dev@example.com')
    requestHeaders.set('x-user-name', 'Developer')

    return NextResponse.next({
      request: {
        headers: requestHeaders
      }
    })
  }

  // Check for auth token
  const token = request.cookies.get('auth_token_server')?.value

  // For API routes, verify token validity
  if (request.nextUrl.pathname.startsWith('/ui/api/')) {
    if (!token) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      )
    }

    // Verify token validity
    const tokenPayload = verifyToken(token)
    if (!tokenPayload) {
      return NextResponse.json(
        { error: 'Invalid or expired token' },
        { status: 401 }
      )
    }

    // Add user info to headers for API routes
    const requestHeaders = new Headers(request.headers)
    requestHeaders.set('x-user-email', tokenPayload.email)
    requestHeaders.set('x-user-name', tokenPayload.name)

    return NextResponse.next({
      request: {
        headers: requestHeaders
      }
    })
  }

  // For page routes, let the client-side handle auth
  return NextResponse.next()
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    '/((?!_next/static|_next/image|favicon.ico).*)',
  ],
}