'use client'

import { useAuth } from '../contexts/AuthContext'

export default function AuthButton() {
  const { isAuthenticated, isLoading, user, login, logout } = useAuth()

  if (isLoading) {
    return (
      <button className="px-4 py-2 text-sm font-medium text-gray-500 bg-gray-100 rounded-md" disabled>
        Loading...
      </button>
    )
  }

  if (isAuthenticated && user) {
    return (
      <div className="flex items-center gap-3">
        <span className="text-sm text-gray-600">{user.displayName || user.email}</span>
        <button
          onClick={logout}
          className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 transition-colors"
        >
          Sign Out
        </button>
      </div>
    )
  }

  return (
    <button
      onClick={login}
      className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors"
    >
      Sign In with Azure AD
    </button>
  )
}