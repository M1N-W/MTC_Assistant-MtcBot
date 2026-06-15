import "server-only";

export function isAdminProxyMutation(method: string): boolean {
  return !["GET", "HEAD"].includes(method.toUpperCase());
}
