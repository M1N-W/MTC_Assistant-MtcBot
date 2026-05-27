import { NextRequest } from "next/server";
import { isAuthenticated } from "@/lib/auth";

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "content-encoding",
  "content-length",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

async function proxy(request: NextRequest, context: RouteContext) {
  if (!(await isAuthenticated())) {
    return Response.json(
      { error: { code: "UNAUTHORIZED", message: "Dashboard session is required." } },
      { status: 401 },
    );
  }

  const apiBase = process.env.MTC_BOT_API_BASE_URL || "http://127.0.0.1:5000";
  const apiToken = process.env.MTC_DASHBOARD_API_TOKEN || "";
  if (!apiToken) {
    return Response.json(
      { error: { code: "API_TOKEN_NOT_CONFIGURED", message: "MTC_DASHBOARD_API_TOKEN is missing." } },
      { status: 503 },
    );
  }

  const { path } = await context.params;
  const upstreamUrl = new URL(`/api/admin/${path.join("/")}`, apiBase);
  request.nextUrl.searchParams.forEach((value, key) => upstreamUrl.searchParams.set(key, value));

  const headers = new Headers();
  headers.set("Authorization", `Bearer ${apiToken}`);
  headers.set("Accept", "application/json");
  if (request.headers.get("content-type")) {
    headers.set("Content-Type", request.headers.get("content-type") || "application/json");
  }

  const init: RequestInit = {
    method: request.method,
    headers,
    cache: "no-store",
  };
  if (!["GET", "HEAD"].includes(request.method)) {
    init.body = await request.arrayBuffer();
  }

  let upstream: Response;
  try {
    upstream = await fetch(upstreamUrl, {
      ...init,
      signal: AbortSignal.timeout(8_000),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown network error";
    return Response.json(
      {
        error: {
          code: "BOT_API_UNREACHABLE",
          message: `Could not reach Flask bot API at ${apiBase}. Start the bot API or set MTC_BOT_API_BASE_URL to the running Flask service. (${message})`,
        },
      },
      { status: 502 },
    );
  }
  const responseHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      responseHeaders.set(key, value);
    }
  });
  responseHeaders.set("Cache-Control", "no-store");

  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export async function GET(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}
