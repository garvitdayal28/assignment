export default function RawJson({ turn }) {
  const payload = turn
    ? {
        status: turn.status,
        state: turn.state,
        missing: turn.missing,
        assumptions: turn.assumptions,
        intent: turn.intent,
        extraction: turn.extraction,
        recommendations: turn.recommendations,
      }
    : {};

  return (
    <>
      <pre className="scroll-slim overflow-x-auto rounded-lg border border-line bg-[#0b1013] p-2.5 text-[11.5px] text-[#b9cbd6]">
        {JSON.stringify(payload, null, 2)}
      </pre>
      <p className="mt-2.5 text-[11.5px] text-faint">
        The structured payload emitted alongside every guest-facing reply.
      </p>
    </>
  );
}
