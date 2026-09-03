const BUBBLE = {
  guest: "self-end rounded-tr-sm bg-guest",
  bot: "self-start rounded-tl-sm bg-raised",
  error: "self-start rounded-tl-sm bg-danger",
};

export default function MessageBubble({ message }) {
  return (
    <>
      <div
        className={`max-w-[88%] rounded-xl px-3.5 py-2.5 leading-relaxed break-words whitespace-pre-wrap sm:max-w-[78%] ${BUBBLE[message.role]}`}
      >
        {message.text}
      </div>
      {message.role === "bot" ? (
        <p className="-mt-1 self-start text-[11px] text-mute">
          {message.status}
          {message.extraction ? ` · ${message.extraction}` : ""}
        </p>
      ) : null}
    </>
  );
}
