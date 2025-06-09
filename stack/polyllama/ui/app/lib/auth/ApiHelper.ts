import { NextRequest } from "next/server";
import { Token } from "./jwt";

class ApiHelper {
  static async GetToken(req: NextRequest): Promise<Token | null> {
    try {
      const tokenFromCookie = req.cookies.get("auth_token_server")?.value;
      if (!tokenFromCookie) {
        return null;
      }
      return new Token(tokenFromCookie);
    } catch (error) {
      console.error("Error getting token:", error);
      return null;
    }
  }
}

export default ApiHelper;