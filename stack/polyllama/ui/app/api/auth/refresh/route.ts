import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { verifyToken, createTokenPair } from "../../../lib/auth/jwt";

export async function POST(req: NextRequest) {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get("refresh_token_server")?.value;

  if (!refreshToken) {
    return NextResponse.json(
      { error: "No refresh token found" },
      { status: 401 }
    );
  }

  // Verify refresh token
  const payload = verifyToken(refreshToken);
  
  if (!payload || payload.type !== 'refresh') {
    return NextResponse.json(
      { error: "Invalid refresh token" },
      { status: 401 }
    );
  }

  try {
    // Generate new token pair
    const { accessToken, refreshToken: newRefreshToken } = await createTokenPair(
      payload.email,
      payload.name,
    );

    // Set new access token
    cookieStore.set("auth_token_server", accessToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 15 * 60, // 15 minutes
    });

    // Set new refresh token
    cookieStore.set("refresh_token_server", newRefreshToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 7 * 24 * 60 * 60, // 7 days
    });

    return NextResponse.json({ 
      success: true,
      accessToken, // Return for client-side storage if needed
    });
  } catch (error) {
    console.error("Token refresh error:", error);
    return NextResponse.json(
      { error: "Failed to refresh token" },
      { status: 500 }
    );
  }
}