export function formatMoney(amount: string | number, currency = "BWP") {
  return `${currency} ${Number(amount).toFixed(2)}`;
}
