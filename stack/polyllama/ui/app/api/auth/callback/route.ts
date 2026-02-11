import { ConfidentialClientApplication, INetworkModule } from "@azure/msal-node";
import { NextRequest, NextResponse } from "next/server";
import { createTokenPair } from "../../../lib/auth/jwt";
import { getRedirectUri } from "../../../lib/auth/config";

// Custom network client for Next.js API routes
class NextJsNetworkClient implements INetworkModule {
  async sendGetRequestAsync<T>(
    url: string,
    options?: any
  ): Promise<T> {
    const response = await fetch(url, {
      method: 'GET',
      headers: options?.headers || {},
    });

    const body = await response.json();

    // Return NetworkResponse structure expected by MSAL
    return {
      headers: Object.fromEntries(response.headers.entries()),
      body,
      status: response.status,
    } as T;
  }

  async sendPostRequestAsync<T>(
    url: string,
    options?: any
  ): Promise<T> {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        ...options?.headers,
      },
      body: options?.body,
    });

    const body = await response.json();

    console.log('OAuth token response:', {
      status: response.status,
      error: body.error,
      error_description: body.error_description,
    });

    // Return NetworkResponse structure expected by MSAL
    return {
      headers: Object.fromEntries(response.headers.entries()),
      body,
      status: response.status,
    } as T;
  }
}

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
    system: {
      loggerOptions: {
        loggerCallback(loglevel: any, message: any, containsPii: any) {
          console.log("[MSAL]", message);
        },
        piiLoggingEnabled: false,
        logLevel: 3, // Verbose
      },
      networkClient: new NextJsNetworkClient(),
    },
  };

  const pca = new ConfidentialClientApplication(msalConfig);
  const tokenRequest = {
    code,
    scopes: ["user.read", "mail.read", "mail.readwrite", "mail.send"],
    redirectUri: getRedirectUri(baseDomain),
  };

  console.log("Token request config:", {
    authority: msalConfig.auth.authority,
    redirectUri: tokenRequest.redirectUri,
    scopes: tokenRequest.scopes,
  });

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

    let accessToken, refreshToken;
    try {
      const tokenPair = await createTokenPair(
        userName,
        response.account!.name ?? "Unnamed User"
      );
      accessToken = tokenPair.accessToken;
      refreshToken = tokenPair.refreshToken;
    } catch (tokenError) {
      console.error("Error creating token pair:", tokenError);
      return NextResponse.json(
        { 
          error: "Token Creation Failed", 
          message: tokenError instanceof Error ? tokenError.message : "Failed to create authentication tokens"
        },
        { status: 500 },
      );
    }

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

    // Store Graph access token in a separate cookie
    if (response.accessToken) {
      redirectResponse.cookies.set("graph_token", response.accessToken, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        path: "/",
        maxAge: 1 * 60 * 60, // 1 hour in seconds
      });
    }

    return redirectResponse;
  } catch (error) {
    console.error("Callback error:", error);
    
    const errorObj = error as { errorCode?: string; errorMessage?: string; correlationId?: string; stack?: string };
    console.error("Error details:", {
      errorCode: errorObj.errorCode,
      errorMessage: errorObj.errorMessage,
      correlationId: errorObj.correlationId,
      stack: errorObj.stack,
    });

    // Provide more specific error responses
    if (errorObj.errorCode === "request_cannot_be_made") {
      return NextResponse.json(
        {
          error: "Authentication Failed",
          message: "Invalid or missing authorization code",
          details: errorObj.errorMessage
        },
        { status: 400 },
      );
    }

    return NextResponse.json(
      {
        error: "Internal Server Error",
        message: errorObj.errorMessage || "Authentication failed",
        errorCode: errorObj.errorCode
      },
      { status: 500 },
    );
  }
}