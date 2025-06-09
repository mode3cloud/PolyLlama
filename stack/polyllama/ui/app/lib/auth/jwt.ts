import jwt from 'jsonwebtoken';

export interface TokenPayload {
  email: string;
  name: string;
  iat?: number;
  exp?: number;
  type?: 'access' | 'refresh';
}

export class Token {
  private _token: string;
  private _payload: TokenPayload;

  constructor(token: string) {
    this._token = token;
    const decoded = jwt.decode(token) as TokenPayload;
    if (!decoded) {
      throw new Error('Invalid token');
    }
    this._payload = decoded;
  }

  get token(): string {
    return this._token;
  }

  get payload(): TokenPayload {
    return this._payload;
  }

  tokenHasExpired(): boolean {
    if (!this._payload.exp) return false;
    return Date.now() >= this._payload.exp * 1000;
  }

  // Check if token will expire soon (within 5 minutes)
  tokenExpiresSoon(): boolean {
    if (!this._payload.exp) return false;
    const fiveMinutesFromNow = Date.now() + (5 * 60 * 1000);
    return fiveMinutesFromNow >= this._payload.exp * 1000;
  }

  isRefreshToken(): boolean {
    return this._payload.type === 'refresh';
  }
}

export async function createToken(
  email: string,
  name: string,
  expirationMinutes: number,
  type: 'access' | 'refresh' = 'access'
): Promise<string> {
  const secret = process.env.JWT_SECRET;
  if (!secret) {
    throw new Error('JWT_SECRET not configured');
  }

  const payload: TokenPayload = {
    email,
    name,
    type,
  };

  return jwt.sign(payload, secret, {
    expiresIn: `${expirationMinutes}m`,
  });
}

export async function createTokenPair(
  email: string,
  name: string
): Promise<{ accessToken: string; refreshToken: string }> {
  // Access token: 15 minutes
  const accessToken = await createToken(email, name, 15, 'access');
  
  // Refresh token: 7 days
  const refreshToken = await createToken(email, name, 7 * 24 * 60, 'refresh');
  
  return { accessToken, refreshToken };
}

export function verifyToken(token: string): TokenPayload | null {
  const secret = process.env.JWT_SECRET;
  if (!secret) {
    throw new Error('JWT_SECRET not configured');
  }

  try {
    return jwt.verify(token, secret) as TokenPayload;
  } catch {
    return null;
  }
}