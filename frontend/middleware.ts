/**
 * Next.js middleware — Local-First masaüstü modu.
 *
 * Eskiden /dashboard için refreshToken yoksa /login'e atıyordu.
 * Kişisel kokpitte giriş zorunluluğu yoktur; istekler olduğu gibi geçer.
 */
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(_request: NextRequest) {
  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/login", "/register"],
};
