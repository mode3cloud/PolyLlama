type FetchOptions = RequestInit & {
  skipAuth?: boolean
}

export async function fetchWithAuth(url: string, options: FetchOptions = {}): Promise<Response> {
  const { skipAuth = false, ...fetchOptions } = options

  // Make the request
  const response = await fetch(url, fetchOptions)

  // If we get a 401 and auth handling is not skipped
  if (response.status === 401 && !skipAuth) {
    // Check if we're in a browser context
    if (typeof window !== 'undefined') {
      // Import auth context dynamically to avoid SSR issues
      const { useAuth } = await import('../contexts/AuthContext')
      
      // We can't use hooks directly here, so we'll dispatch a custom event
      window.dispatchEvent(new CustomEvent('auth:unauthorized'))
    }
  }

  return response
}

// Helper to create a fetch wrapper that automatically handles auth
export function createAuthFetch() {
  return (url: string, options?: FetchOptions) => fetchWithAuth(url, options)
}