import { ASSUMPTION_NOTES } from "../lib/format.js";
import OptionCard from "./OptionCard.jsx";
import RawJson from "./RawJson.jsx";
import Section from "./Section.jsx";
import SlotTable from "./SlotTable.jsx";
import StatusPill from "./StatusPill.jsx";

export default function StatePanel({ hotel, turn }) {
  const currency = hotel?.currency ?? "INR";
  const options = turn?.recommendations ?? [];
  const assumptions = turn?.assumptions ?? [];

  return (
    <aside className="scroll-slim flex flex-col gap-6 overflow-y-auto bg-shell px-5 pt-4 pb-10">
      <Section title="Turn status">
        <StatusPill status={turn?.status} />
      </Section>

      <Section title="Known state">
        <SlotTable state={turn?.state} missing={turn?.missing} />
      </Section>

      {assumptions.length > 0 ? (
        <Section title="Assumptions">
          <ul className="space-y-1.5">
            {assumptions.map((note) => (
              <li
                key={note}
                className="rounded-md bg-amber-dim px-2.5 py-1.5 text-xs text-[#f5d67f]"
              >
                Assumed {ASSUMPTION_NOTES[note] ?? note}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      <Section
        title="Ranked options"
        meta={options.length ? `(${options.length})` : null}
      >
        {options.length === 0 ? (
          <p className="text-[11.5px] text-faint">
            Nothing to recommend until dates and guest count are known.
          </p>
        ) : (
          <ul className="space-y-2">
            {options.map((option) => (
              <OptionCard
                key={option.rank}
                option={option}
                currency={currency}
              />
            ))}
          </ul>
        )}
      </Section>

      <Section title="Raw turn JSON">
        <RawJson turn={turn} />
      </Section>
    </aside>
  );
}
