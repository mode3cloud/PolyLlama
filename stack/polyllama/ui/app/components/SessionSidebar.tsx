'use client'

import { useState, useEffect } from 'react'
import { fetchWithAuth } from '../lib/fetchWithAuth'

interface Session {
  id: string
  created_at: string
  message_count: number
  title?: string
  first_message?: string
}

interface SessionSidebarProps {
  currentSessionId: string
  onSessionSelect: (sessionId: string) => void
  onNewSession: () => void
  refreshTrigger?: number
}

export default function SessionSidebar({ currentSessionId, onSessionSelect, onNewSession, refreshTrigger }: SessionSidebarProps) {
  const [sessions, setSessions] = useState<Session[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isDeleting, setIsDeleting] = useState<string | null>(null)

  const fetchSessions = async () => {
    try {
      setIsLoading(true)
      const response = await fetchWithAuth('/ui/api/chat/sessions')
      if (response.ok) {
        const data = await response.json()
        setSessions(data.sessions || [])
      }
    } catch (error) {
      console.error('Failed to fetch sessions:', error)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchSessions()
  }, [currentSessionId, refreshTrigger])

  const deleteSession = async (sessionId: string) => {
    if (isDeleting || !confirm('Are you sure you want to delete this session?')) return
    
    try {
      setIsDeleting(sessionId)
      const response = await fetchWithAuth(`/ui/api/chat/sessions?session_id=${sessionId}`, {
        method: 'DELETE'
      })
      
      if (response.ok) {
        const remainingSessions = sessions.filter(s => s.id !== sessionId)
        setSessions(remainingSessions)
        
        if (sessionId === currentSessionId) {
          // Find the next session to select
          const currentIndex = sessions.findIndex(s => s.id === sessionId)
          let nextSession = null
          
          // Try to select the next session in the list
          if (currentIndex < sessions.length - 1) {
            nextSession = sessions[currentIndex + 1]
          } else if (currentIndex > 0) {
            // If we're at the end, select the previous session
            nextSession = sessions[currentIndex - 1]
          }
          
          if (nextSession && remainingSessions.some(s => s.id === nextSession.id)) {
            onSessionSelect(nextSession.id)
          } else {
            // No other sessions, create a new one
            onNewSession()
          }
        }
      }
    } catch (error) {
      console.error('Failed to delete session:', error)
    } finally {
      setIsDeleting(null)
    }
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    
    return date.toLocaleDateString()
  }

  const getSessionTitle = (session: Session) => {
    if (session.title) return session.title
    
    // Generate a title based on creation time and message count
    const date = new Date(session.created_at)
    const time = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    
    if (session.message_count > 0) {
      return `Chat at ${time}`
    }
    return `New chat at ${time}`
  }

  return (
    <div className="w-64 bg-gray-900 text-white h-full flex flex-col">
      <div className="p-4 border-b border-gray-700">
        <button
          onClick={onNewSession}
          className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg flex items-center justify-center gap-2 transition-colors"
        >
          <span className="text-lg">+</span>
          <span>New Chat</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="p-4 text-center text-gray-400">
            Loading sessions...
          </div>
        ) : sessions.length === 0 ? (
          <div className="p-4 text-center text-gray-400">
            No chat sessions yet
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {sessions.map(session => (
              <div
                key={session.id}
                className={`group relative rounded-lg transition-colors ${
                  session.id === currentSessionId
                    ? 'bg-gray-700'
                    : 'hover:bg-gray-800'
                }`}
              >
                <button
                  onClick={() => onSessionSelect(session.id)}
                  className="w-full text-left px-3 py-2"
                >
                  <div className="text-sm font-medium truncate">
                    {getSessionTitle(session)}
                  </div>
                  <div className="text-xs text-gray-400 flex items-center gap-2">
                    <span>{formatDate(session.created_at)}</span>
                    <span>•</span>
                    <span>{session.message_count} messages</span>
                  </div>
                </button>
                
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    deleteSession(session.id)
                  }}
                  disabled={isDeleting === session.id}
                  className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-gray-700 rounded"
                  title="Delete session"
                >
                  {isDeleting === session.id ? (
                    <span className="text-gray-400">...</span>
                  ) : (
                    <span className="text-red-400">🗑</span>
                  )}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="p-4 border-t border-gray-700 text-xs text-gray-400">
        <div>Current session:</div>
        <div className="font-mono truncate">{currentSessionId}</div>
      </div>
    </div>
  )
}