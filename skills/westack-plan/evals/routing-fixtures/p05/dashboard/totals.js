export function revenueLabel(cents) {
  return "$" + (cents / 100).toFixed(2);
}
