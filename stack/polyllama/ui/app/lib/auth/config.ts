export function getRedirectUri(): string {
  // Check if we're in development mode
  const isDev = process.env.NODE_ENV === 'development';
  
  // Use dev redirect URI if available and in dev mode
  if (isDev && process.env.AZURE_AD_REDIRECT_URI_DEV) {
    return process.env.AZURE_AD_REDIRECT_URI_DEV;
  }
  
  // Otherwise use the standard redirect URI
  return process.env.AZURE_AD_REDIRECT_URI || '';
}