import { SLOTS, formatSlot } from "../lib/format.js";

export default function SlotTable({ state, missing = [] }) {
  return (
    <table className="w-full border-collapse">
      <tbody>
        {SLOTS.map(({ key, label }) => {
          const value = state ? formatSlot(key, state[key]) : null;
          const needed = missing.includes(key);
          return (
            <tr key={key}>
              <td className="w-[42%] border-b border-hairline py-1.5 align-top text-mute">
                {label}
              </td>
              <td
                className={`border-b border-hairline py-1.5 align-top tabular-nums ${
                  value ? "" : needed ? "text-amber" : "text-faint"
                }`}
              >
                {value ?? (needed ? "needed" : "—")}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
