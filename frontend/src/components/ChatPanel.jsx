import { useEffect, useRef } from "react";

import Composer from "./Composer.jsx";
import MessageBubble from "./MessageBubble.jsx";
import SamplePrompts from "./SamplePrompts.jsx";
import TypingIndicator from "./TypingIndicator.jsx";

export default function ChatPanel({ messages, busy, onSend, active }) {
  const logRef = useRef(null);

  // `active` is a dependency because a hidden panel has no scroll height:
  // the log has to be pinned again when the tab comes back into view.
  useEffect(() => {
    const log = logRef.current;
    if (log) log.scrollTop = log.scrollHeight;
  }, [messages, busy, active]);

  return (
    <div
      className={`${active ? "flex" : "hidden"} min-h-0 flex-col border-line lg:flex lg:border-r`}
    >
      <div
        ref={logRef}
        className="scroll-slim flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto p-4 sm:p-5"
      >
        {messages.length === 0 ? (
          <div className="m-auto max-w-[340px] text-center text-mute">
            Say something vague, in English or Hinglish.
            <br />
            The agent holds context across turns and only asks for what is
            missing.
          </div>
        ) : null}

        {messages.map((message, index) => (
          <MessageBubble key={index} message={message} />
        ))}

        {busy ? <TypingIndicator /> : null}
      </div>

      <SamplePrompts onPick={onSend} disabled={busy} />
      <Composer onSend={onSend} disabled={busy} />
    </div>
  );
}
