export default function Section({ title, meta, children, className = "" }) {
  return (
    <section className={className}>
      <h2 className="mb-2 flex items-baseline gap-2 text-[11px] font-semibold tracking-[0.09em] text-mute uppercase">
        {title}
        {meta ? (
          <span className="font-normal tracking-normal normal-case">
            {meta}
          </span>
        ) : null}
      </h2>
      {children}
    </section>
  );
}
