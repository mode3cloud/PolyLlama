/**
 * Wrapper around fetch that includes credentials for authentication
 * This ensures cookies (including auth tokens) are sent with requests
 */
export async function fetchWithAuth(url: string, options?: RequestInit): Promise<Response> {
  // Ensure we're using the correct base URL when behind a proxy
  const fullUrl = url.startsWith('http') ? url : `${window.location.origin}${url}`;
  
  return fetch(fullUrl, {
    ...options,
    credentials: 'include',
    headers: {
      ...options?.headers,
    },
  });
}