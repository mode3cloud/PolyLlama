'use client';

import { useAuth } from '../lib/auth/AuthContext';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

export default function LoginPage() {
  const { user, loading, login } = useAuth();
  const router = useRouter();

  useEffect(() => {
    // If already logged in, redirect to home
    if (!loading && user) {
      router.push('/');
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl flex items-center justify-center text-4xl mx-auto mb-4">
            🦙
          </div>
          <h2 className="mt-6 text-3xl font-extrabold text-gray-900">
            PolyLlama
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            Dynamic Multi-Instance Orchestration
          </p>
        </div>
        <div className="bg-white py-8 px-4 shadow sm:rounded-lg sm:px-10">
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-medium text-gray-900">
                Sign in to continue
              </h3>
              <p className="mt-1 text-sm text-gray-600">
                Use your Azure AD account to access PolyLlama
              </p>
            </div>
            <button
              onClick={login}
              className="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
            >
              <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd" />
              </svg>
              Sign in with Azure AD
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}