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

  useEffect(() => {
    let live = true;
    fetchHotel()
      .then((data) => live && setHotel(data))
      .catch(() => live && setHotel({ unreachable: true }));
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
