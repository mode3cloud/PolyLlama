'use client';

import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { fetchWithAuth } from '../fetchWithAuth';

interface User {
  email: string;
  name: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const decodeToken = (token: string) => {
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      return JSON.parse(jsonPayload);
    } catch (error) {
      console.error('Failed to decode token:', error);
      return null;
    }
  };

  const refreshToken = useCallback(async () => {
    try {
      const response = await fetchWithAuth('/ui/api/auth/refresh', {
        method: 'POST',
      });

      if (response.ok) {
        await response.json();
        // Re-check auth to get updated user info
        await checkAuth();
        return true;
      }
      return false;
    } catch (error) {
      console.error('Token refresh failed:', error);
      return false;
    }
  }, []);

  const checkAuth = useCallback(async () => {
    try {
      const response = await fetchWithAuth('/ui/api/auth/get_token');
      if (response.ok) {
        const token = await response.json();
        const payload = decodeToken(token);

        if (payload) {
          setUser({ email: payload.email, name: payload.name });

          // Calculate time until token expires
          const now = Date.now() / 1000;
          const expiresIn = payload.exp - now;

          // Refresh token 1 minute before it expires
          const refreshIn = Math.max(0, (expiresIn - 60) * 1000);

          // Clear any existing interval
          if (refreshIntervalRef.current) {
            clearTimeout(refreshIntervalRef.current);
          }

          // Set up automatic refresh
          if (refreshIn > 0) {
            refreshIntervalRef.current = setTimeout(() => {
              refreshToken();
            }, refreshIn);
          }
        }
      }
    } catch (error) {
      console.error('Auth check failed:', error);
    } finally {
      setLoading(false);
    }
  }, [refreshToken]);

  useEffect(() => {
    checkAuth();

    // Cleanup on unmount
    return () => {
      if (refreshIntervalRef.current) {
        clearTimeout(refreshIntervalRef.current);
      }
    };
  }, [checkAuth]);

  const login = () => {
    const protocol = window.location.protocol;
    const host = window.location.hostname;
    const port = window.location.port;
    let fullDomain = `${protocol}//${host}`;
    if (
      (protocol === 'http:' && port && port !== '80') ||
      (protocol === 'https:' && port && port !== '443')
    ) {
      fullDomain += `:${port}`;
    }
    console.log(fullDomain);
    window.location.href = '/ui/api/auth/login?baseDomain=' + encodeURIComponent(fullDomain);
  };

  const logout = async () => {
    // Clear refresh interval
    if (refreshIntervalRef.current) {
      clearTimeout(refreshIntervalRef.current);
    }

    try {
      await fetchWithAuth('/ui/api/auth/logout');
    } catch (error) {
      console.error('Logout error:', error);
    }
    
    setUser(null);
    window.location.href = '/ui';
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}