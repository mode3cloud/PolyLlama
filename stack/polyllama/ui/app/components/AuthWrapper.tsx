'use client';

interface AuthWrapperProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export default function AuthWrapper({ children }: AuthWrapperProps) {
  // For now, just return children directly since AuthGuard doesn't exist
  // TODO: Implement proper authentication when AuthGuard is available
  return <>{children}</>;
}