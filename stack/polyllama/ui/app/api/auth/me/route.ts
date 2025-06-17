import { NextRequest, NextResponse } from 'next/server'
import jwt from 'jsonwebtoken'

export async function GET(request: NextRequest) {
  const token = request.cookies.get('auth-token')?.value

  if (!token) {
    return NextResponse.json(
      { error: 'Not authenticated' },
      { status: 401 }
    )
  }

  const jwtSecret = process.env.JWT_SECRET
  if (!jwtSecret) {
    return NextResponse.json(
      { error: 'Server configuration error' },
      { status: 500 }
    )
  }

  try {
    const decoded = jwt.verify(token, jwtSecret) as any
    
    return NextResponse.json({
      email: decoded.email,
      displayName: decoded.displayName,
      userId: decoded.userId,
    })
  } catch (error) {
    // Token is invalid or expired
    return NextResponse.json(
      { error: 'Invalid token' },
      { status: 401 }
    )
  }
}