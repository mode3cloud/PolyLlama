import { NextRequest } from "next/server";

export function getOriginalBaseURL(req: NextRequest): string {
  const proto = req.headers.get("x-forwarded-proto") || "http";
  const host = req.headers.get("x-forwarded-host") || req.headers.get("host") || "localhost";
  return `${proto}://${host}`;
}