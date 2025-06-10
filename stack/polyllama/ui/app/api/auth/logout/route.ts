import { NextRequest, NextResponse } from "next/server";
import { ConfidentialClientApplication } from "@azure/msal-node";
import { cookies } from "next/headers";
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
  const accounts = await pca.getTokenCache().getAllAccounts();
  
  accounts.forEach((account) => {
    pca.getTokenCache().removeAccount(account);
  });
  
  const cookieStore = await cookies();
  cookieStore.delete("auth_token_server");
  cookieStore.delete("refresh_token_server");
  
  return NextResponse.redirect(
    new URL("/ui", getOriginalBaseURL(req)).toString(),
  );
}