'use client'

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'

interface AuthContextType {
  isAuthenticated: boolean
  isLoading: boolean
  user: any | null
  login: () => void
  logout: () => void
  checkAuth: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [user, setUser] = useState<any | null>(null)

  const checkAuth = async () => {
    try {
      const response = await fetch('/ui/api/auth/me')
      if (response.ok) {
        const userData = await response.json()
        setIsAuthenticated(true)
        setUser(userData)
      } else {
        setIsAuthenticated(false)
        setUser(null)
      }
    } catch (error) {
      console.error('Error checking auth:', error)
      setIsAuthenticated(false)
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }

  const login = () => {
    // Get the current base URL to pass as baseDomain
    const currentUrl = window.location.origin
    window.location.href = `/ui/api/auth/login?baseDomain=${encodeURIComponent(currentUrl)}`
  }

  const logout = async () => {
    try {
      await fetch('/ui/api/auth/logout')
      setIsAuthenticated(false)
      setUser(null)
      window.location.href = '/'
    } catch (error) {
      console.error('Error logging out:', error)
    }
  }

  useEffect(() => {
    checkAuth()
  }, [])

  // Show loading state
  if (isLoading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900">
        <div className="text-white">Loading...</div>
      </div>
    )
  }

  // Show login screen if not authenticated
  if (!isAuthenticated) {
    return (
      <AuthContext.Provider value={{ isAuthenticated, isLoading, user, login, logout, checkAuth }}>
        <div className="fixed inset-0 z-50 overflow-y-auto bg-gray-900">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:max-w-lg sm:w-full">
              <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                <div className="sm:flex sm:items-start">
                  <div className="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-blue-100 sm:mx-0 sm:h-10 sm:w-10">
                    <svg className="h-6 w-6 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                  </div>
                  <div className="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left">
                    <h3 className="text-lg leading-6 font-medium text-gray-900">
                      Welcome to PolyLlama
                    </h3>
                    <div className="mt-2">
                      <p className="text-sm text-gray-500">
                        Please sign in with your Azure AD account to access the application.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
              <div className="bg-gray-50 px-4 py-3 sm:px-6 text-center">
                <button
                  type="button"
                  onClick={login}
                  className="inline-flex justify-center rounded-md border border-transparent shadow-sm px-6 py-3 bg-blue-600 text-base font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Sign In with Azure AD
                </button>
              </div>
            </div>
          </div>
        </div>
      </AuthContext.Provider>
    )
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, user, login, logout, checkAuth }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}