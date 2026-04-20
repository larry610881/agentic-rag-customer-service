/**
 * 將 amount 格式化為 currency 顯示字串。
 * - amount 接受 string（Decimal serialized）或 number
 * - 預設 TWD，無小數位（保留 2 位 max）
 *
 * 範例：
 *   formatCurrency("1500") -> "TWD 1,500"
 *   formatCurrency(3500.5, "USD") -> "USD 3,500.5"
 */
export function formatCurrency(
  amount: string | number,
  currency = "TWD",
): string {
  const n = typeof amount === "string" ? Number(amount) : amount;
  if (Number.isNaN(n)) return String(amount);
  return `${currency} ${n.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}

/**
 * 純數字千分位（不含 currency prefix）。
 */
export function formatAmount(amount: string | number): string {
  const n = typeof amount === "string" ? Number(amount) : amount;
  if (Number.isNaN(n)) return String(amount);
  return n.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
}
