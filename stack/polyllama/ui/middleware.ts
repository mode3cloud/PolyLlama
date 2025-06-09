import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import ApiHelper from "./app/lib/auth/ApiHelper";

export async function middleware(req: NextRequest) {
  const url = req.nextUrl;

  // Protect all API routes under /api/ except auth routes
  if (
    url.pathname.startsWith("/api/") &&
    !url.pathname.startsWith("/api/auth/login") &&
    !url.pathname.startsWith("/api/auth/logout") &&
    !url.pathname.startsWith("/api/auth/callback") &&
    !url.pathname.startsWith("/api/auth/get_token") &&
    !url.pathname.startsWith("/api/auth/refresh")
  ) {
    const token = await ApiHelper.GetToken(req);
    if (!token || token.tokenHasExpired()) {
      console.log("Token is invalid or has expired", req.url);
      return new NextResponse(null, { status: 401 });
    }
  }
  
  return NextResponse.next();
}

export const config = {
  matcher: "/api/:path*",
};