/**
 * Debug configuration for development
 * Set DEBUG_STREAMING=true in environment or localStorage to enable streaming logs
 */

let debugStreamingEnabled: boolean | null = null;

export const isStreamingDebugEnabled = (): boolean => {
  if (debugStreamingEnabled === null) {
    // Check environment variable first
    if (typeof process !== 'undefined' && process.env?.DEBUG_STREAMING === 'true') {
      debugStreamingEnabled = true;
    }
    // Check localStorage for browser-side override
    else if (typeof window !== 'undefined') {
      const localStorageValue = localStorage.getItem('DEBUG_STREAMING');
      debugStreamingEnabled = localStorageValue === 'true';
    }
    // Default to false
    else {
      debugStreamingEnabled = false;
    }
  }
  
  return debugStreamingEnabled;
};

export const setStreamingDebug = (enabled: boolean): void => {
  debugStreamingEnabled = enabled;
  if (typeof window !== 'undefined') {
    localStorage.setItem('DEBUG_STREAMING', enabled.toString());
  }
};

export const debugLog = (message: string, ...args: any[]): void => {
  if (isStreamingDebugEnabled()) {
    console.log(message, ...args);
  }
};