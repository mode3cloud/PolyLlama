'use client'

import { useCallback, useState } from 'react'

interface HeaderProps {
  onRefresh: () => void;
}

export default function Header({ onRefresh }: HeaderProps) {
  const [isSpinning, setIsSpinning] = useState(false)

  const handleRefresh = useCallback(() => {
    setIsSpinning(true)
    setTimeout(() => {
      setIsSpinning(false)
    }, 1000)
    onRefresh()
  }, [onRefresh])

  return (
    <header className="bg-white/95 backdrop-blur-md border-b border-gray-200 sticky top-0 z-[100]">
      <div className="max-w-[1400px] mx-auto px-4 md:px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3 text-2xl font-bold text-gray-900">
          <div className="w-10 h-10 bg-gradient-to-br from-primary to-primary-dark rounded-lg flex items-center justify-center text-2xl">
            🦙
          </div>
          <span>PolyLlama</span>
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
        </div>
      </div>
    </header>
  )
}