export default function TypingIndicator() {
  return (
    <div className="flex max-w-[78%] items-center gap-1 self-start rounded-xl rounded-tl-sm bg-raised px-3.5 py-3">
      {[0, 1, 2].map((index) => (
        <span
          key={index}
          className="size-1.5 animate-blink rounded-full bg-mute"
          style={{ animationDelay: `${index * 0.2}s` }}
        />
      ))}
    </div>
  );
}
