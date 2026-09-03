// The backend emits stable keys (`cheapest`, `weekend_sat_sun`, …) rather than
// prose, so each surface words them itself. This is the dashboard's wording;
// response.py has its own, in English and Hinglish.

export const OPTION_LABELS = {
  cheapest: "Cheapest",
  fewest_rooms: "Fewest rooms",
  most_space: "Most space",
  alternative: "Alternative",
  best_fit: "Best fit",
};

export const ASSUMPTION_NOTES = {
  weekend_sat_sun: "weekend = Saturday to Sunday, 1 night",
};

export const SLOTS = [
  { key: "check_in", label: "Check-in" },
  { key: "check_out", label: "Check-out" },
  { key: "nights", label: "Nights" },
  { key: "party_size", label: "Headcount given" },
  { key: "adults", label: "Adults" },
  { key: "children", label: "Children" },
  { key: "children_ages", label: "Children ages" },
  { key: "rooms_wanted", label: "Rooms asked for" },
  { key: "ac_preference", label: "AC preference" },
  { key: "special_requests", label: "Special requests" },
  { key: "language", label: "Language" },
];

export const SAMPLE_PROMPTS = [
  "Room available for tomorrow?",
  "2 rooms, 15th to 17th, 4 adults, AC",
  "kal ke liye room chahiye, 3 log hain",
  "AC room chahiye",
  "We are 7 people, 2 kids aged 4 and 6, need rooms this weekend",
  "Do you have a swimming pool?",
];

const SYMBOLS = { INR: "₹", USD: "$", EUR: "€" };

export function money(amount, currency = "INR") {
  const symbol = SYMBOLS[currency] ?? `${currency} `;
  return symbol + Number(amount).toLocaleString("en-IN");
}

const AC_PREFERENCES = { ac: "AC", non_ac: "Non-AC", any: "No preference" };

export function isEmpty(value) {
  return (
    value === null ||
    value === undefined ||
    value === "" ||
    (Array.isArray(value) && value.length === 0)
  );
}

export function formatSlot(key, value) {
  if (isEmpty(value)) return null;
  if (Array.isArray(value)) return value.join(", ");
  if (key === "ac_preference") return AC_PREFERENCES[value] ?? value;
  return String(value);
}

export function describeRooms(option) {
  return option.rooms
    .map((room) => {
      const beds = room.extra_beds
        ? ` +${room.extra_beds} extra bed${room.extra_beds > 1 ? "s" : ""}`
        : "";
      return `${room.count}× ${room.type}${beds}`;
    })
    .join("  +  ");
}

export function plural(count, word) {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}
