// Helper to get the API base URL
export const getApiUrl = (path: string) => {
  // When running in browser, use relative URLs
  // This allows the app to work behind reverse proxies
  if (typeof window !== 'undefined') {
    // Log for debugging
    console.log('Browser API call - original path:', path);
    
    // Remove /ui prefix if present since we're already under /ui
    const cleanPath = path.startsWith('/ui/') ? path.substring(3) : path
    console.log('Browser API call - cleaned path:', cleanPath);
    
    return cleanPath
  }
  
  // Server-side: use absolute URL
  const cleanPath = path.startsWith('/') ? path.substring(1) : path
  return `http://localhost:11434/${cleanPath}`
}