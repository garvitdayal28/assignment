import { OPTION_LABELS, describeRooms, money, plural } from "../lib/format.js";

export default function OptionCard({ option, currency }) {
  const top = option.rank === 1;
  return (
    <li
      className={`rounded-lg border bg-panel px-3 py-2.5 ${top ? "border-brand-dim" : "border-line"}`}
    >
      <div className="flex items-baseline gap-2">
        <span className="text-xs text-mute">#{option.rank}</span>
        <span className="rounded bg-raised px-1.5 py-0.5 text-[11px] text-mute">
          {OPTION_LABELS[option.label] ?? option.label}
        </span>
        <span className="ml-auto font-semibold text-brand tabular-nums">
          {money(option.total_price, currency)}
        </span>
      </div>

      <p className="mt-1">{describeRooms(option)}</p>

      <p className="mt-0.5 text-xs text-mute">
        {money(option.per_night, currency)}/night × {option.nights} · sleeps{" "}
        {option.capacity}
        {option.extra_beds
          ? ` · ${plural(option.extra_beds, "extra bed")}`
          : ""}
      </p>
    </li>
  );
}
