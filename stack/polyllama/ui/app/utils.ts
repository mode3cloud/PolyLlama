// Helper to get the API base URL
export const getApiUrl = (path: string) => {
  // Remove leading slash if present
  const cleanPath = path.startsWith('/') ? path.substring(1) : path
  return `http://localhost:11434/${cleanPath}`
}