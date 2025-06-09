import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../lib/auth/AuthContext';

export function useAuthGuard() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      // Redirect to login page instead of showing login UI inline
      router.push('/login');
    }
  }, [user, loading, router]);

  return { isAuthenticated: !!user, isLoading: loading };
}