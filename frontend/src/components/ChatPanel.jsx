import { useEffect, useRef } from "react";

import Composer from "./Composer.jsx";
import MessageBubble from "./MessageBubble.jsx";
import SamplePrompts from "./SamplePrompts.jsx";
import TypingIndicator from "./TypingIndicator.jsx";

export default function ChatPanel({ messages, busy, onSend }) {
  const logRef = useRef(null);

  useEffect(() => {
    const log = logRef.current;
    if (log) log.scrollTop = log.scrollHeight;
  }, [messages, busy]);

  return (
    <div className="flex min-h-0 flex-col border-line lg:border-r">
      <div
        ref={logRef}
        className="scroll-slim flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto p-5"
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
