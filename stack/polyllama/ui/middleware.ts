import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import ApiHelper from "./app/lib/auth/ApiHelper";

export async function middleware(req: NextRequest) {
  const url = req.nextUrl;

  // With basePath '/ui', the paths in middleware are relative to the basePath
  // So /ui/api/auth/login appears as /api/auth/login here
  
  console.log(`[Middleware] Path: ${url.pathname}, Full URL: ${req.url}`);
  console.log(`[Middleware] Cookies:`, req.cookies.getAll());
  
  // Protect all API routes under /api/ except auth routes
  if (
    url.pathname.startsWith("/api/") &&
    !url.pathname.startsWith("/api/auth/login") &&
    !url.pathname.startsWith("/api/auth/logout") &&
    !url.pathname.startsWith("/api/auth/callback") &&
    !url.pathname.startsWith("/api/auth/get_token") &&
    !url.pathname.startsWith("/api/auth/refresh")
  ) {
    console.log(`[Middleware] Checking auth for protected route: ${url.pathname}`);
    const token = await ApiHelper.GetToken(req);
    console.log(`[Middleware] Token found:`, !!token);
    
    if (!token || token.tokenHasExpired()) {
      console.log(`[Middleware] Token is invalid or has expired for ${req.url}`);
      console.log(`[Middleware] Token expired:`, token?.tokenHasExpired());
      return new NextResponse(null, { status: 401 });
    }
    console.log(`[Middleware] Token is valid, proceeding`);
  }
  
  return NextResponse.next();
}

export const config = {
  // The matcher is relative to the basePath, so this matches /ui/api/*
  matcher: "/api/:path*",
};