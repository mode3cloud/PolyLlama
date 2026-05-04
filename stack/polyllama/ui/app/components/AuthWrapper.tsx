'use client';

interface AuthWrapperProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export default function AuthWrapper({ children }: AuthWrapperProps) {
  // Primary authentication is enforced upstream by middleware.ts (JWT + Azure AD,
  // with optional SKIP_AUTH dev bypass). This wrapper is a passthrough placeholder
  // for an additional in-component auth layer (e.g. role-gated rendering) that
  // hasn't been built yet. Safe to use as-is — it does not weaken request-level auth.
  return <>{children}</>;
}