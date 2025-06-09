import { NextRequest } from "next/server";

export function getOriginalBaseURL(req: NextRequest): string {
  // Check for forwarded headers first (when behind nginx/proxy)
  const forwardedProto = req.headers.get("x-forwarded-proto");
  const forwardedHost = req.headers.get("x-forwarded-host");
  
  if (forwardedProto && forwardedHost) {
    return `${forwardedProto}://${forwardedHost}`;
  }
  
  // Fallback to direct host header
  const proto = req.headers.get("x-scheme") || req.nextUrl.protocol.replace(':', '');
  const host = req.headers.get("host") || req.nextUrl.host;
  
  // For development, ensure we keep the port
  if (host === "localhost" && !host.includes(":")) {
    return `${proto}://localhost:11434`;
  }
  
  return `${proto}://${host}`;
}