'use client'

import { useState } from 'react'
import Header from '../components/Header'
import ChatInterface from '../components/ChatInterface'
import AuthGuard from '../components/AuthGuard'

export default function ChatPage() {
  const [refreshKey, setRefreshKey] = useState(0)

  const handleRefresh = () => {
    setRefreshKey(prev => prev + 1)
  }

  return (
    <AuthGuard>
      <div className="h-screen flex flex-col">
        <div className="flex-shrink-0">
          <Header onRefresh={handleRefresh} />
        </div>
        <div className="flex-1 overflow-hidden">
          <ChatInterface key={refreshKey} onRefresh={handleRefresh} />
        </div>
      </div>
    </AuthGuard>
  )
}