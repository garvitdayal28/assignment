import { useState } from "react";

import ChatPanel from "./components/ChatPanel.jsx";
import Header from "./components/Header.jsx";
import StatePanel from "./components/StatePanel.jsx";
import { useConversation } from "./hooks/useConversation.js";

function Tab({ id, label, badge, view, onSelect }) {
  const active = view === id;
  return (
    <button
      type="button"
      onClick={() => onSelect(id)}
      aria-current={active ? "page" : undefined}
      className={`flex flex-1 items-center justify-center gap-2 border-b-2 py-2.5 text-[13px] transition-colors ${
        active
          ? "border-brand text-slate-100"
          : "border-transparent text-mute hover:text-slate-100"
      }`}
    >
      {label}
      {badge ? (
        <span className="rounded-full bg-raised px-1.5 py-0.5 text-[10px] text-mute">
          {badge}
        </span>
      ) : null}
    </button>
  );
}

export default function App() {
  const { hotel, messages, turn, busy, send, reset } = useConversation();
  // Below lg the two panels are tabs: a chat squeezed into half a phone
  // screen is unusable, and the inspector below it is unreachable.
  const [view, setView] = useState("chat");

  return (
    <div className="flex h-full flex-col">
      <Header
        hotel={hotel}
        onReset={reset}
        canReset={messages.length > 0 && !busy}
      />

      <nav className="flex shrink-0 border-b border-line bg-panel px-2 lg:hidden">
        <Tab id="chat" label="Chat" view={view} onSelect={setView} />
        <Tab
          id="state"
          label="State"
          badge={turn?.status ?? null}
          view={view}
          onSelect={setView}
        />
      </nav>

      <main className="grid min-h-0 flex-1 grid-cols-1 grid-rows-1 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <ChatPanel
          messages={messages}
          busy={busy}
          onSend={send}
          active={view === "chat"}
        />
        <StatePanel hotel={hotel} turn={turn} active={view === "state"} />
      </main>
    </div>
  );
}
