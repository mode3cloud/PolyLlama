import { NextRequest, NextResponse } from "next/server";

export async function GET(req: NextRequest) {
  const tokenFromServerCookie = req.cookies.get("auth_token_server")?.value;

  if (tokenFromServerCookie === undefined) {
    return NextResponse.json(
      { error: "No token found in your cookie from Azure login" },
      { status: 401 }
    );
  }
  
  return NextResponse.json(tokenFromServerCookie, { status: 200 });
}