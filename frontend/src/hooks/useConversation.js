import { useCallback, useEffect, useRef, useState } from "react";

import { fetchHotel, resetSession, sendMessage } from "../lib/api.js";

/**
 * Owns the whole client side of a conversation: the message log, the latest
 * structured turn from the backend, and the in-flight flag. Deliberately not
 * persisted anywhere -- a refresh unmounts this and the conversation is gone.
 */
export function useConversation() {
  const [hotel, setHotel] = useState(null);
  const [messages, setMessages] = useState([]);
  const [turn, setTurn] = useState(null);
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);

  // A free-tier API host sleeps when idle and can take the best part of a
  // minute to wake, so a failed first call is retried before the header is
  // allowed to say the API is down.
  useEffect(() => {
    let live = true;

    async function load(attempt = 0) {
      try {
        const data = await fetchHotel();
        if (live) setHotel(data);
      } catch {
        if (!live) return;
        if (attempt < 4) {
          setHotel({ waking: true });
          setTimeout(() => live && load(attempt + 1), 4000);
        } else {
          setHotel({ unreachable: true });
        }
      }
    }

    load();
    return () => {
      live = false;
    };
  }, []);

  const send = useCallback(async (text) => {
    const message = text.trim();
    if (!message || inFlight.current) return;

    inFlight.current = true;
    setBusy(true);
    setMessages((prev) => [...prev, { role: "guest", text: message }]);

    try {
      const data = await sendMessage(message);
      setTurn(data);
      setMessages((prev) => [
        ...prev,
        {
          role: "bot",
          text: data.reply,
          status: data.status,
          extraction: data.extraction,
        },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: "error", text: `Request failed — ${error.message}` },
      ]);
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }, []);

  const reset = useCallback(async () => {
    await resetSession().catch(() => {});
    setMessages([]);
    setTurn(null);
  }, []);

  return { hotel, messages, turn, busy, send, reset };
}
