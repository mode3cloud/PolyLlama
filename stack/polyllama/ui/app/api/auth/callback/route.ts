import { ConfidentialClientApplication } from "@azure/msal-node";
import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createTokenPair } from "../../../lib/auth/jwt";
import { getRedirectUri } from "../../../lib/auth/config";

export async function GET(req: NextRequest) {
  if (
    process.env.AZURE_AD_CLIENT_ID === undefined ||
    process.env.AZURE_AD_TENANT_ID === undefined ||
    process.env.AZURE_AD_CLIENT_SECRET === undefined
  ) {
    return NextResponse.json(
      { error: "Internal Server Error" },
      { status: 500 },
    );
  }

  const state = req.nextUrl.searchParams.get("state");
  const code = req.nextUrl.searchParams.get("code");
  const baseDomain = state ? decodeURIComponent(state) : undefined;

  // Debug logging
  console.log("Auth callback received:", {
    state,
    code: code ? "present" : "missing",
    redirectUri: getRedirectUri(baseDomain),
    searchParams: req.nextUrl.searchParams.toString(),
  });

  // Validate code parameter
  if (!code) {
    console.error("Missing authorization code in callback");
    return NextResponse.json(
      { error: "Bad Request", message: "Missing authorization code" },
      { status: 400 },
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
    code,
    scopes: ["user.read"],
    redirectUri: getRedirectUri(baseDomain),
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

    // Create redirect response
    const redirectResponse = baseDomain
      ? NextResponse.redirect(`${baseDomain}/ui`)
      : NextResponse.redirect(new URL("/ui", req.url));

    // Set cookies on the redirect response
    redirectResponse.cookies.set("auth_token_server", accessToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 1 * 60 * 60, // 1 hour in seconds
    });

    redirectResponse.cookies.set("refresh_token_server", refreshToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 7 * 24 * 60 * 60, // 7 days in seconds
    });

    return redirectResponse;
  } catch (error: any) {
    console.error("Callback error:", error);
    console.error("Error details:", {
      errorCode: error.errorCode,
      errorMessage: error.errorMessage,
      correlationId: error.correlationId,
      stack: error.stack,
    });

    // Provide more specific error responses
    if (error.errorCode === "request_cannot_be_made") {
      return NextResponse.json(
        {
          error: "Authentication Failed",
          message: "Invalid or missing authorization code",
          details: error.errorMessage
        },
        { status: 400 },
      );
    }

    return NextResponse.json(
      {
        error: "Internal Server Error",
        message: error.errorMessage || "Authentication failed",
        errorCode: error.errorCode
      },
      { status: 500 },
    );
  }
}