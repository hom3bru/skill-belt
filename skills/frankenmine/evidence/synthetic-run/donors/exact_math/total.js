// Authored synthetic donor, fixture revision math-v1. Rights: task-authored example.
// Decimal strings preserve integers beyond Number.MAX_SAFE_INTEGER.
export function total(decimalStrings) {
  return decimalStrings.reduce((sum, value) => sum + BigInt(value), 0n).toString();
}
