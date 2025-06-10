import { ConfidentialClientApplication } from "@azure/msal-node";
import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createTokenPair } from "../../../lib/auth/jwt";
import { getOriginalBaseURL } from "../../../lib/auth/utils";
import { getRedirectUri } from "../../../lib/auth/config";

export async function GET(req: NextRequest) {
  const redirectUri = getRedirectUri(req.headers);
  
  if (
    process.env.AZURE_AD_CLIENT_ID === undefined ||
    process.env.AZURE_AD_TENANT_ID === undefined ||
    process.env.AZURE_AD_CLIENT_SECRET === undefined ||
    !redirectUri
  ) {
    return NextResponse.json(
      { error: "Internal Server Error" },
      { status: 500 },
    );
  }

  const msalConfig = {
    auth: {
      clientId: process.env.AZURE_AD_CLIENT_ID,
      authority: `https://login.microsoftonline.com/${process.env.AZURE_AD_TENANT_ID}`,
      clientSecret: process.env.AZURE_AD_CLIENT_SECRET,
    },
  };

  const pca = new ConfidentialClientApplication(msalConfig);
  const tokenRequest = {
    code: req.nextUrl.searchParams.get("code") as string,
    scopes: ["user.read"],
    redirectUri: redirectUri,
  };

  try {
    const response = await pca.acquireTokenByCode(tokenRequest);
    const userName = response.account!.username;
    
    if (!userName) {
      console.error("No username found in auth response");
      return NextResponse.json(
        { error: "Internal Server Error" },
        { status: 500 },
      );
    }
    
    const allowedUsers =
      process.env.AZURE_AD_ALLOWED_USERS?.toLowerCase().split(";") ?? [];
    const allowedDomains =
      process.env.AZURE_AD_ALLOWED_DOMAINS?.toLowerCase().split(";") ?? [];
    const userDomain = userName.toLowerCase().split("@")[1];
    
    if (
      !allowedUsers.includes(userName.toLowerCase()) &&
      !allowedDomains.includes(userDomain)
    ) {
      return NextResponse.json({ error: "Forbidden" }, { status: 403 });
    }

    const { accessToken, refreshToken } = await createTokenPair(
      userName,
      response.account!.name ?? "Unnamed User",
    );
    
    console.log("User authenticated:", userName);
    const cookieStore = await cookies();
    
    // Set access token (15 minutes)
    cookieStore.set("auth_token_server", accessToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 15 * 60, // 15 minutes in seconds
    });
    
    // Set refresh token (7 days)
    cookieStore.set("refresh_token_server", refreshToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 7 * 24 * 60 * 60, // 7 days in seconds
    });
    
    return NextResponse.redirect(
      new URL("/ui", getOriginalBaseURL(req)).toString(),
    );
  } catch (error: any) {
    console.error("Callback error:", error);
    return NextResponse.json(
      { error: "Internal Server Error", errorMessage: error.errorMessage },
      { status: 500 },
    );
  }
}