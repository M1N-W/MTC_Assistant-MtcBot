export async function GET() {
  return Response.json({
    status: "healthy",
    service: "mtc-dashboard",
    commit: process.env.RENDER_GIT_COMMIT || process.env.VERCEL_GIT_COMMIT_SHA || "unknown",
    timestamp: new Date().toISOString(),
  });
}
