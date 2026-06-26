/** Compact credit count like Apollo UI: 4391 → "4.3K". */
export function formatApolloCredits(value) {
  if (value == null || Number.isNaN(Number(value))) return "—";
  const n = Number(value);
  if (n >= 1_000_000) {
    const m = Math.floor(n / 100_000) / 10;
    return `${m}M`;
  }
  if (n >= 1000) {
    const k = Math.floor(n / 100) / 10;
    return `${k}K`;
  }
  return n.toLocaleString();
}
