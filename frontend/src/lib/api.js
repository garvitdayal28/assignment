// One session id per page load, held in this module variable only. Nothing is
// written to localStorage, sessionStorage or a cookie, so a browser refresh
// starts a brand new conversation and the server drops the old one.
export const SESSION_ID =
  typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : String(Date.now()) + Math.random().toString(16).slice(2);

async function request(path, options) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => null);
  if (!response.ok || !data) {
    throw new Error(data?.error || `${response.status} ${response.statusText}`);
  }
  if (data.error) throw new Error(data.error);
  return data;
}

const json = (body) => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const fetchHotel = () => request("/api/hotel");

export const sendMessage = (message) =>
  request("/chat", json({ message, session_id: SESSION_ID }));

export const resetSession = () =>
  request("/reset", json({ session_id: SESSION_ID }));
