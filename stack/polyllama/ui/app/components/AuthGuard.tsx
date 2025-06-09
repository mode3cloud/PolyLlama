'use client';

import { useAuth } from '../lib/auth/AuthContext';

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, loading, login } = useAuth();

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

  if (!user) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="max-w-md w-full space-y-8">
          <div className="text-center">
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
                  Authentication Required
                </h3>
                <p className="mt-1 text-sm text-gray-600">
                  Please sign in with your Azure AD account to continue.
                </p>
              </div>
              <button
                onClick={login}
                className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Sign in with Azure AD
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}