export function getRedirectUri(baseDomain?: string | null): string {
  // Get the redirect path from environment variable
  const redirectPath = '/ui/api/auth/callback';
  if (!baseDomain) return redirectPath;
  // Decode baseDomain in case it's URL encoded
  const decodedBaseDomain = decodeURIComponent(baseDomain.toString());
  // Use URL constructor to safely join baseDomain and redirectPath
  const url = new URL(redirectPath, decodedBaseDomain);
  return url.toString();

}