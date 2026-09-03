import { useState } from "react";

export default function Composer({ onSend, disabled }) {
  const [draft, setDraft] = useState("");

  function submit(event) {
    event.preventDefault();
    if (!draft.trim() || disabled) return;
    onSend(draft);
    setDraft("");
  }

  return (
    <form
      onSubmit={submit}
      className="flex shrink-0 gap-2 border-t border-line bg-panel px-5 py-3"
    >
      <input
        type="text"
        value={draft}
        autoFocus
        onChange={(event) => setDraft(event.target.value)}
        placeholder="kal ke liye 2 room chahiye AC wala"
        className="min-w-0 flex-1 rounded-lg border border-line bg-raised px-3 py-2.5 outline-none placeholder:text-faint focus:border-brand"
      />
      <button
        type="submit"
        disabled={disabled || !draft.trim()}
        className="rounded-lg bg-brand px-4 py-2.5 text-[13px] font-semibold text-brand-deep disabled:opacity-50"
      >
        Send
      </button>
    </form>
  );
}
