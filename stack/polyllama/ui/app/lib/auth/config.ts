export function getRedirectUri(headers?: Headers): string {
  // Get the redirect path from environment variable
  const redirectPath = process.env.AZURE_AD_REDIRECT_URI_PATH || '/ui/api/auth/callback';
  
  // If headers are provided, construct the full URL dynamically
  if (headers) {
    const proto = headers.get('x-forwarded-proto') || 'http';
    const host = headers.get('x-forwarded-host') || headers.get('host') || 'localhost:11434';
    
    return `${proto}://${host}${redirectPath}`;
  }
  
  // Fallback to legacy behavior if no headers provided
  // This ensures backward compatibility during migration
  const isDev = process.env.NODE_ENV === 'development';
  if (isDev && process.env.AZURE_AD_REDIRECT_URI_DEV) {
    return process.env.AZURE_AD_REDIRECT_URI_DEV;
  }
  
  return process.env.AZURE_AD_REDIRECT_URI || '';
}