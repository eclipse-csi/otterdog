// Helpers for the json values of the evaluations of the playground.

export const isObject = (value) => value !== null && typeof value === "object" && !Array.isArray(value);

export const isScalar = (value) => value === null || typeof value !== "object";

// a value on one line, shortened if it is longer than a length
export function formatValue(value, length = 120) {
  const text = JSON.stringify(value);
  return text.length > length ? text.slice(0, length - 1) + "…" : text;
}
