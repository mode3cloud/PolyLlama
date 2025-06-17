import { NextRequest } from 'next/server'
import jwt from 'jsonwebtoken'

export function verifyAuth(request: NextRequest): { valid: boolean; user?: any } {
  const token = request.cookies.get('auth-token')?.value

  if (!token) {
    return { valid: false }
  }

  const jwtSecret = process.env.JWT_SECRET
  if (!jwtSecret) {
    return { valid: false }
  }

  try {
    const decoded = jwt.verify(token, jwtSecret) as any
    return { valid: true, user: decoded }
  } catch (error) {
    return { valid: false }
  }
}