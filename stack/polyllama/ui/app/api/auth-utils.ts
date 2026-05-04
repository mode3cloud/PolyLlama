import { NextRequest } from 'next/server'
import jwt from 'jsonwebtoken'

interface AuthUser {
  email: string;
  name: string;
}

export function verifyAuth(request: NextRequest): { valid: boolean; user?: AuthUser } {
  // Development mode bypass
  if (process.env.SKIP_AUTH === 'true') {
    return {
      valid: true,
      user: {
        email: 'dev@example.com',
        name: 'Developer'
      }
    }
  }

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
    const decoded = jwt.verify(token, jwtSecret) as AuthUser
    return { valid: true, user: decoded }
  } catch (error) {
    console.error('Auth verification failed: JWT verification error', error)
    return { valid: false }
  }
}