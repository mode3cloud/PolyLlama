'use client';

import { useAuth } from '../lib/auth/AuthContext';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

interface AuthWrapperProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export default function AuthWrapper({ children, fallback }: AuthWrapperProps) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace('/login');
    }
  }, [user, loading, router]);

  // Show nothing while checking auth to prevent flash
  if (loading || !user) {
    return (
      <>
        {fallback || (
          <div className="min-h-screen bg-gray-50 flex items-center justify-center">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
              <p className="mt-4 text-gray-600">Authenticating...</p>
            </div>
          </div>
        )}
      </>
    );
  }

  return <>{children}</>;
}