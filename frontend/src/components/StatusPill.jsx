const STYLES = {
  gathering: "bg-amber-dim text-amber",
  recommending: "bg-sky-dim text-sky",
  confirmed: "bg-brand-dim text-brand",
  idle: "bg-raised text-mute",
};

export default function StatusPill({ status }) {
  const key = status ?? "idle";
  return (
    <span
      className={`inline-block rounded-full px-3 py-1 text-xs font-semibold tracking-wide ${STYLES[key] ?? STYLES.idle}`}
    >
      {status ?? "no messages yet"}
    </span>
  );
}
