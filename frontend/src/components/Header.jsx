import { plural } from "../lib/format.js";

function LlmBadge({ hotel }) {
  if (!hotel) return null;
  if (hotel.unreachable) {
    return (
      <span className="flex items-center gap-2 text-xs text-amber">
        <span className="size-2 rounded-full bg-amber" />
        API unreachable
      </span>
    );
  }
  const ready = hotel.llm === "ready";
  return (
    <span
      className="flex items-center gap-2 text-xs text-mute"
      title={hotel.llm}
    >
      <span
        className={`size-2 rounded-full ${ready ? "bg-brand" : "bg-amber"}`}
      />
      {ready ? hotel.model : "rules-only fallback"}
    </span>
  );
}

export default function Header({ hotel, onReset, canReset }) {
  const subtitle = hotel?.unreachable
    ? "Start the Flask API with: python main.py"
    : hotel
      ? `${plural(hotel.rooms.length, "room type")} from inventory.json · check-in ${hotel.check_in_time}, check-out ${hotel.check_out_time}`
      : "";

  return (
    <header className="flex shrink-0 items-center gap-4 border-b border-line bg-panel px-5 py-3">
      <div className="min-w-0">
        <h1 className="truncate text-[15px] font-semibold">
          {hotel?.hotel_name ?? (hotel?.unreachable ? "No API" : "Loading…")}
          <span className="font-normal text-mute"> · booking agent</span>
        </h1>
        <p className="truncate text-xs text-mute">{subtitle}</p>
      </div>

      <div className="ml-auto flex items-center gap-4">
        <LlmBadge hotel={hotel} />
        <button
          type="button"
          onClick={onReset}
          disabled={!canReset}
          className="rounded-md border border-line bg-raised px-3 py-1.5 text-[13px] transition-colors hover:border-mute disabled:opacity-50 disabled:hover:border-line"
        >
          New conversation
        </button>
      </div>
    </header>
  );
}
