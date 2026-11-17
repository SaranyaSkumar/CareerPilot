export async function workspaceFetch(input: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(input, { ...init, cache: "no-store" });
  if (response.status === 401 && typeof window !== "undefined") {
    const next = `${window.location.pathname}${window.location.search}`;
    window.location.assign(`/login?next=${encodeURIComponent(next)}`);
  }
  return response;
}
