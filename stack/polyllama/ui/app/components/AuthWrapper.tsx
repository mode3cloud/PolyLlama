'use client';

import AuthGuard from './AuthGuard';

interface AuthWrapperProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export default function AuthWrapper({ children, fallback }: AuthWrapperProps) {
  return <AuthGuard>{children}</AuthGuard>;
}