import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  const tenantId = process.env.AZURE_AD_TENANT_ID
  const clientId = process.env.AZURE_AD_CLIENT_ID
  const redirectUri = `${process.env.POLYLLAMA_UI_BASE_URL || 'http://localhost:3000'}/ui/api/auth/callback`
  
  if (!tenantId || !clientId) {
    return NextResponse.json(
      { error: 'Azure AD configuration missing' },
      { status: 500 }
    )
  }

  // Azure AD OAuth2 authorization URL
  const authUrl = new URL(`https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/authorize`)
  authUrl.searchParams.append('client_id', clientId)
  authUrl.searchParams.append('response_type', 'code')
  authUrl.searchParams.append('redirect_uri', redirectUri)
  authUrl.searchParams.append('response_mode', 'query')
  authUrl.searchParams.append('scope', 'openid profile email')
  authUrl.searchParams.append('state', generateState())

  return NextResponse.redirect(authUrl.toString())
}

function generateState(): string {
  return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15)
}