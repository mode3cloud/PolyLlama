'use client'

import EmailInterface from '../components/EmailInterface'
import Header from '../components/Header'
import AuthWrapper from '../components/AuthWrapper'

export default function EmailPage() {
  const handleRefresh = () => {
    // Email interface handles its own refresh
    window.location.reload()
  }

  return (
    <AuthWrapper>
      <div className="min-h-screen flex flex-col">
        <div className="fixed top-0 left-0 right-0 z-50">
          <Header onRefresh={handleRefresh} />
        </div>
        <main className="flex-1 mt-16">
          <EmailInterface />
        </main>
      </div>
    </AuthWrapper>
  )
}