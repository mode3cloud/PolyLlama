import { NextRequest } from 'next/server'
import jwt from 'jsonwebtoken'

export function verifyAuth(request: NextRequest): { valid: boolean; user?: any } {
  const token = request.cookies.get('auth_token_server')?.value

  if (!token) {
    console.error('Auth verification failed: No token found in cookies')
    return { valid: false }
  }

  const jwtSecret = process.env.JWT_SECRET
  if (!jwtSecret) {
    console.error('Auth verification failed: JWT_SECRET not found in environment')
    return { valid: false }
  }

  try {
    const decoded = jwt.verify(token, jwtSecret) as any
    return { valid: true, user: decoded }
  } catch (error) {
    console.error('Auth verification failed: JWT verification error', error)
    return { valid: false }
  }
}