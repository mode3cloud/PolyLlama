/**
 * Server-side fetch wrapper that includes POLYLLAMA_API_KEY for router API calls
 * This should only be used in server-side API routes
 */
export async function serverFetch(url: string, options?: RequestInit): Promise<Response> {
  const headers: Record<string, string> = {
    ...(options?.headers as Record<string, string>),
  };

  // Add API key for calls to the router
  if (url.includes('router:11434') && process.env.POLYLLAMA_API_KEY) {
    headers['api-key'] = process.env.POLYLLAMA_API_KEY;
  }

  return fetch(url, {
    ...options,
    headers,
  });
}