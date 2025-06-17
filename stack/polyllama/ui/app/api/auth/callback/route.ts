import { NextRequest, NextResponse } from 'next/server'
import jwt from 'jsonwebtoken'

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const code = searchParams.get('code')
  const state = searchParams.get('state')

  if (!code) {
    return NextResponse.redirect(new URL('/?error=auth_failed', request.url))
  }

  const tenantId = process.env.AZURE_AD_TENANT_ID
  const clientId = process.env.AZURE_AD_CLIENT_ID
  const clientSecret = process.env.AZURE_AD_CLIENT_SECRET
  const redirectUri = `${process.env.POLYLLAMA_UI_BASE_URL || 'http://localhost:3000'}/ui/api/auth/callback`

  if (!tenantId || !clientId || !clientSecret) {
    return NextResponse.redirect(new URL('/?error=server_config', request.url))
  }

  try {
    // Exchange code for token
    const tokenUrl = `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/token`
    const tokenResponse = await fetch(tokenUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        client_id: clientId,
        client_secret: clientSecret,
        code: code,
        redirect_uri: redirectUri,
        grant_type: 'authorization_code',
      }),
    })

    if (!tokenResponse.ok) {
      console.error('Token exchange failed:', await tokenResponse.text())
      return NextResponse.redirect(new URL('/?error=token_exchange_failed', request.url))
    }

    const tokenData = await tokenResponse.json()
    const idToken = tokenData.id_token

    // Decode the ID token to get user info
    const decodedToken = jwt.decode(idToken) as any

    // Check if user is allowed
    const allowedUsers = process.env.AZURE_AD_ALLOWED_USERS?.split(',').map(u => u.trim()) || []
    const allowedDomains = process.env.AZURE_AD_ALLOWED_DOMAINS?.split(',').map(d => d.trim()) || []

    const userEmail = decodedToken.email || decodedToken.preferred_username
    const userDomain = userEmail?.split('@')[1]

    const isAllowed = 
      allowedUsers.length === 0 && allowedDomains.length === 0 ||
      allowedUsers.includes(userEmail) ||
      (userDomain && allowedDomains.includes(userDomain))

    if (!isAllowed) {
      return NextResponse.redirect(new URL('/?error=unauthorized', request.url))
    }

    // Create our own JWT for session management
    const jwtSecret = process.env.JWT_SECRET
    if (!jwtSecret) {
      return NextResponse.redirect(new URL('/?error=jwt_config', request.url))
    }

    const sessionToken = jwt.sign(
      {
        email: userEmail,
        displayName: decodedToken.name,
        userId: decodedToken.oid,
      },
      jwtSecret,
      { expiresIn: '24h' }
    )

    // Set cookie and redirect to home
    const response = NextResponse.redirect(new URL('/', request.url))
    response.cookies.set('auth-token', sessionToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 60 * 60 * 24, // 24 hours
    })

    return response
  } catch (error) {
    console.error('Auth callback error:', error)
    return NextResponse.redirect(new URL('/?error=auth_error', request.url))
  }
}