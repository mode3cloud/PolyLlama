'use client'

import { useCallback, useState } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { useAuth } from '../lib/auth/AuthContext'

interface HeaderProps {
  onRefresh: () => void;
}

export default function Header({ onRefresh }: HeaderProps) {
  const [isSpinning, setIsSpinning] = useState(false)
  const [showUserMenu, setShowUserMenu] = useState(false)
  const pathname = usePathname()
  const router = useRouter()
  const { user, logout } = useAuth()

  const handleRefresh = useCallback(() => {
    setIsSpinning(true)
    setTimeout(() => {
      setIsSpinning(false)
    }, 1000)
    onRefresh()
  }, [onRefresh])

  const isActiveTab = (path: string) => {
    if (path === '/' && pathname === '/') return true
    if (path !== '/' && pathname.startsWith(path)) return true
    return false
  }

  return (
    <header className="bg-white/95 backdrop-blur-md border-b border-gray-200 h-16">
      <div className="max-w-[1400px] mx-auto px-4 md:px-8 h-full flex items-center justify-between">
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-3 text-2xl font-bold text-gray-900">
            <div className="w-10 h-10 bg-gradient-to-br from-primary to-primary-dark rounded-lg flex items-center justify-center text-2xl">
              🦙
            </div>
            <span>PolyLlama</span>
          </div>
          
          {/* Navigation Tabs */}
          <nav className="flex gap-2">
            <button
              onClick={() => router.push('/')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActiveTab('/') 
                  ? 'bg-blue-100 text-blue-700 border border-blue-200' 
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
              }`}
            >
              Dashboard
            </button>
            <button
              onClick={() => router.push('/chat')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActiveTab('/chat') 
                  ? 'bg-blue-100 text-blue-700 border border-blue-200' 
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
              }`}
            >
              Chat
            </button>
          </nav>
        </div>
        
        <div className="flex gap-4 items-center">
          <button 
            className="px-4 py-2 bg-white border border-gray-300 rounded-md cursor-pointer text-sm flex items-center gap-2 transition-all hover:bg-gray-50 hover:border-gray-400"
            onClick={handleRefresh}
          >
            <span className={`inline-block transition-transform ${isSpinning ? 'animate-spin-once' : ''}`}>
              ↻
            </span>
            <span>Refresh</span>
          </button>
          
          {user && (
            <div className="relative">
              <button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-md transition-colors"
              >
                <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center text-white font-medium">
                  {user.name.charAt(0).toUpperCase()}
                </div>
                <span className="hidden md:block">{user.name}</span>
              </button>
              
              {showUserMenu && (
                <div className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg py-1 z-50">
                  <div className="px-4 py-2 text-sm text-gray-700 border-b">
                    <div className="font-medium">{user.name}</div>
                    <div className="text-gray-500 text-xs">{user.email}</div>
                  </div>
                  <button
                    onClick={logout}
                    className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                  >
                    Sign out
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  )
}