/**
 * Para ve yüzde biçimlendirme — karanlık terminal için mono-dostu çıktılar.
 *
 * BIST → ₺ (tr-TR) · ABD → $ (en-US) · TRY karşılıkları gri alt satırda.
 */

/** TRY tutarını Türkçe para formatına çevirir. Örn: ₺1.234,56 */
export function formatTry(value: number | null | undefined): string {
  const amount = Number.isFinite(value) ? Number(value) : 0;
  return new Intl.NumberFormat("tr-TR", {
    style: "currency",
    currency: "TRY",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

/** USD tutarını Amerikan formatında gösterir. Örn: $225.50 */
export function formatUsd(value: number | null | undefined): string {
  const amount = Number.isFinite(value) ? Number(value) : 0;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

/**
 * Para birimine göre biçimlendirir.
 * @param currency 'TRY' | 'USD'
 */
export function formatMoney(value: number | null | undefined, currency: string = "TRY"): string {
  return currency.toUpperCase() === "USD" ? formatUsd(value) : formatTry(value);
}

/**
 * İşaretli native K/Z.
 * USD: +$125.50 / -$12.00 · TRY: +₺125,50 / -₺12,00
 */
export function formatSignedMoney(value: number | null | undefined, currency: string = "TRY"): string {
  const amount = Number.isFinite(value) ? Number(value) : 0;
  const isUsd = currency.toUpperCase() === "USD";
  const absBody = isUsd ? formatUsd(Math.abs(amount)) : formatTry(Math.abs(amount));
  if (amount > 0) return `+${absBody}`;
  if (amount < 0) {
    // formatUsd/formatTry zaten $ veya ₺ koyar; eksi için sembolü koru
    return isUsd ? `-$${absBody.replace("$", "")}` : `-₺${absBody.replace("₺", "")}`;
  }
  return absBody;
}

/** Yaklaşık TRY karşılığı (gri alt satır). Örn: ~₺6.130,00 */
export function formatApproxTry(value: number | null | undefined): string {
  return `~${formatTry(value)}`;
}

/** Sayıyı binlik ayırıcılı gösterir (ticker fiyatları). */
export function formatNumber(value: number | null | undefined, digits = 2): string {
  const amount = Number.isFinite(value) ? Number(value) : 0;
  return new Intl.NumberFormat("tr-TR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(amount);
}

/** Yüzdeyi işaretli gösterir. Örn: +6,42% */
export function formatPercent(value: number | null | undefined): string {
  const amount = Number.isFinite(value) ? Number(value) : 0;
  const sign = amount > 0 ? "+" : "";
  return `${sign}${amount.toFixed(2).replace(".", ",")}%`;
}

/**
 * Kâr/zarar rengi — OLED terminal paleti.
 * Pozitif: emerald-400, Negatif: rose-400, Nötr: zinc-500
 */
export function pnlTone(value: number): string {
  if (value > 0) return "text-emerald-400";
  if (value < 0) return "text-rose-400";
  return "text-zinc-500";
}
