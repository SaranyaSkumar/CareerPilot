const BLOCKED_PREFIXES = ["/login", "/signup", "/forgot-password", "/auth/"];

/** Keep post-login redirects inside this app. */
export function safeNext(value: string | null | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) {
    return "/";
  }
  const url = new URL(value, "http://careerpilot.local");
  if (url.origin !== "http://careerpilot.local") return "/";
  if (BLOCKED_PREFIXES.some((prefix) => url.pathname === prefix.slice(0, -1) || url.pathname.startsWith(prefix))) {
    return "/";
  }
  return `${url.pathname}${url.search}`;
}
