import ChatPanel from "./components/ChatPanel.jsx";
import Header from "./components/Header.jsx";
import StatePanel from "./components/StatePanel.jsx";
import { useConversation } from "./hooks/useConversation.js";

export default function App() {
  const { hotel, messages, turn, busy, send, reset } = useConversation();

  return (
    <div className="flex h-full flex-col">
      <Header
        hotel={hotel}
        onReset={reset}
        canReset={messages.length > 0 && !busy}
      />

      <main className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <ChatPanel messages={messages} busy={busy} onSend={send} />
        <StatePanel hotel={hotel} turn={turn} />
      </main>
    </div>
  );
}
