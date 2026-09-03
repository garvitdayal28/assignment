import { SAMPLE_PROMPTS } from "../lib/format.js";

export default function SamplePrompts({ onPick, disabled }) {
  return (
    // On a phone six wrapped chips eat most of the screen, so they scroll
    // sideways in one row instead.
    <div className="scroll-slim flex gap-1.5 overflow-x-auto px-4 pb-2.5 sm:flex-wrap sm:overflow-x-visible sm:px-5">
      {SAMPLE_PROMPTS.map((prompt) => (
        <button
          key={prompt}
          type="button"
          onClick={() => onPick(prompt)}
          disabled={disabled}
          className="shrink-0 rounded-full border border-dashed border-line px-2.5 py-1 text-xs whitespace-nowrap text-mute transition-colors hover:text-slate-100 disabled:opacity-40 disabled:hover:text-mute sm:whitespace-normal"
        >
          {prompt}
        </button>
      ))}
    </div>
  );
}
