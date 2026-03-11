export const normalizeAmount = (value) => {
  if (value === null || value === undefined) return 0;
  const raw = String(value).replaceAll(",", "").trim();
  if (!raw) return 0;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : 0;
};

export const moneyRound = (n) => Math.round((n + Number.EPSILON) * 100) / 100;

export const calcLine = (line) => {
  const qty = normalizeAmount(line.qty);
  const price = normalizeAmount(line.price_unit);
  const discountPct = normalizeAmount(line.discount_pct);
  const iva = normalizeAmount(line.iva_rate);
  const isrRate = line.apply_isr_withholding ? normalizeAmount(line.isr_withholding_rate) : 0;
  const subtotalBeforeDiscount = moneyRound(qty * price);
  const discountAmount = moneyRound(subtotalBeforeDiscount * (discountPct / 100));
  const taxableBase = moneyRound(subtotalBeforeDiscount - discountAmount);
  const ivaAmount = moneyRound(taxableBase * (iva / 100));
  const isrAmount = moneyRound(taxableBase * (isrRate / 100));
  const lineTotal = moneyRound(taxableBase + ivaAmount - isrAmount);
  return { subtotalBeforeDiscount, discountAmount, taxableBase, ivaAmount, isrAmount, lineTotal };
};

export const calcIvaWithholdingAmount = (tax, applyIvaWithholding, ivaWithholdingRate) => {
  if (!applyIvaWithholding) return 0;
  const withholdingRate = normalizeAmount(ivaWithholdingRate);
  if (withholdingRate <= 0) return 0;
  return moneyRound(tax * (withholdingRate / 100));
};
