export async function GET() {
  return Response.json({
    status: "healthy",
    service: "mtc-dashboard",
    timestamp: new Date().toISOString(),
  });
}
