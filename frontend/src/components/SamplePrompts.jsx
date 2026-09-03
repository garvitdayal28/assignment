import { SAMPLE_PROMPTS } from "../lib/format.js";

export default function SamplePrompts({ onPick, disabled }) {
  return (
    <div className="flex flex-wrap gap-1.5 px-5 pb-2.5">
      {SAMPLE_PROMPTS.map((prompt) => (
        <button
          key={prompt}
          type="button"
          onClick={() => onPick(prompt)}
          disabled={disabled}
          className="rounded-full border border-dashed border-line px-2.5 py-1 text-xs text-mute transition-colors hover:text-slate-100 disabled:opacity-40 disabled:hover:text-mute"
        >
          {prompt}
        </button>
      ))}
    </div>
  );
}
