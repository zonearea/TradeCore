import { NextRequest, NextResponse } from "next/server";

const upstream = process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:5080";

async function proxy(request: NextRequest, path: string[]) {
  const target = `${upstream}/api/${path.join("/")}${request.nextUrl.search}`;
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  const cookie = request.headers.get("cookie");

  if (contentType) {
    headers.set("content-type", contentType);
  }

  if (cookie) {
    headers.set("cookie", cookie);
  }

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const upstreamResponse = await fetch(target, {
    method: request.method,
    headers,
    body: hasBody ? await request.arrayBuffer() : undefined,
    cache: "no-store",
  });

  const response = new NextResponse(upstreamResponse.body, {
    status: upstreamResponse.status,
  });
  const responseType = upstreamResponse.headers.get("content-type");

  if (responseType) {
    response.headers.set("content-type", responseType);
  }

  for (const setCookie of upstreamResponse.headers.getSetCookie()) {
    response.headers.append("set-cookie", setCookie);
  }

  return response;
}

type RouteContext = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function POST(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxy(request, path);
}
