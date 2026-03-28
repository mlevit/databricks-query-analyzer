export function humanBytes(b: number | null | undefined): string {
  if (b == null || b === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let val = b;
  while (Math.abs(val) >= 1024 && i < units.length - 1) {
    val /= 1024;
    i++;
  }
  return `${val.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export function formatNumber(n: number | null | undefined): string {
  if (n == null) return "N/A";
  return n.toLocaleString();
}
