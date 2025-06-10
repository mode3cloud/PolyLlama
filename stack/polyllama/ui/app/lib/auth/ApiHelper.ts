import { NextRequest } from "next/server";
import { Token } from "./jwt";

class ApiHelper {
  static async GetToken(req: NextRequest): Promise<Token | null> {
    try {
      console.log("[ApiHelper] Looking for auth_token_server cookie");
      console.log("[ApiHelper] All cookies:", req.cookies.getAll());
      
      const tokenFromCookie = req.cookies.get("auth_token_server")?.value;
      console.log("[ApiHelper] Token from cookie:", tokenFromCookie ? "Found" : "Not found");
      
      if (!tokenFromCookie) {
        return null;
      }
      
      const token = new Token(tokenFromCookie);
      console.log("[ApiHelper] Token created successfully");
      return token;
    } catch (error) {
      console.error("[ApiHelper] Error getting token:", error);
      return null;
    }
  }
}

export default ApiHelper;