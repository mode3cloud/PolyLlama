'use client'

import { useState } from 'react'
import Header from '../components/Header'
import ChatInterface from '../components/ChatInterface'
import AuthWrapper from '../components/AuthWrapper'
import MCPStatus from '../components/MCPStatus'

export default function ChatPage() {
  const [refreshKey, setRefreshKey] = useState(0)

  const handleRefresh = () => {
    setRefreshKey(prev => prev + 1)
  }

  return (
    <AuthWrapper>
      <div className="h-screen flex flex-col">
        <div className="flex-shrink-0">
          <Header onRefresh={handleRefresh} />
        </div>
        <div className="flex-1 overflow-hidden flex">
          <div className="flex-1">
            <ChatInterface key={refreshKey} onRefresh={handleRefresh} />
          </div>
          <div className="w-96 p-4 bg-gray-900 overflow-y-auto">
            <MCPStatus />
          </div>
        </div>
      </div>
    </AuthWrapper>
  )
}