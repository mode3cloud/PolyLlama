type FetchOptions = RequestInit & {
  skipAuth?: boolean
}

export async function fetchWithAuth(url: string, options: FetchOptions = {}): Promise<Response> {
  const { skipAuth = false, ...fetchOptions } = options

  // Ensure credentials are included for cookie-based auth
  const requestOptions: RequestInit = {
    ...fetchOptions,
    credentials: 'same-origin', // Include cookies for same-origin requests
  }

  // Make the request
  const response = await fetch(url, requestOptions)

  // If we get a 401 and auth handling is not skipped
  if (response.status === 401 && !skipAuth) {
    // Check if we're in a browser context
    if (typeof window !== 'undefined') {
      // Reload the page to trigger the auth check
      // This will show the login screen if the user is not authenticated
      window.location.reload()
    }
  }

  return response
}

// Helper to create a fetch wrapper that automatically handles auth
export function createAuthFetch() {
  return (url: string, options?: FetchOptions) => fetchWithAuth(url, options)
}