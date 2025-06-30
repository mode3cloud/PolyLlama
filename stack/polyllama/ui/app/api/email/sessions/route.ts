import { NextRequest, NextResponse } from 'next/server'
import { verifyAuth } from '../../auth-utils'
import { emailStorage } from '../../../lib/emailStorage'

export async function GET(request: NextRequest) {
  // Verify authentication
  const auth = verifyAuth(request)
  if (!auth.valid) {
    return NextResponse.json(
      { error: 'Authentication required' },
      { status: 401 }
    )
  }

  try {
    const { searchParams } = new URL(request.url)
    const emailId = searchParams.get('emailId')

    if (!emailId) {
      return NextResponse.json(
        { error: 'emailId parameter is required' },
        { status: 400 }
      )
    }

    const session = await emailStorage.getSession(emailId)
    
    if (!session) {
      return NextResponse.json(
        { session: null },
        { status: 200 }
      )
    }

    return NextResponse.json({ session })
  } catch (error) {
    console.error('Error fetching email session:', error)
    return NextResponse.json(
      { error: 'Failed to fetch email session' },
      { status: 500 }
    )
  }
}