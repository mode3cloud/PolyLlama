import { ConfidentialClientApplication } from "@azure/msal-node";
import { NextRequest, NextResponse } from "next/server";
import { getRedirectUri } from "../../../lib/auth/config";

export async function GET(req: NextRequest) {
  const baseDomain = req.nextUrl.searchParams.get("baseDomain");

  const redirectUri = getRedirectUri(baseDomain);

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

  const authCodeUrlParameters = {
    scopes: ["user.read"],
    redirectUri: redirectUri,
    state: encodeURIComponent(baseDomain!), // Pass returnUrl in state
  };

  try {
    const response = await pca.getAuthCodeUrl(authCodeUrlParameters);
    return NextResponse.redirect(response);
  } catch (error) {
    console.error("Login error:", error);
    return NextResponse.json(
      { error: "Internal Server Error" },
      { status: 500 },
    );
  }
}