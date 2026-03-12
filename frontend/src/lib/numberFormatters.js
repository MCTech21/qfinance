export const safeNumber = (value) => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

export const safeCurrency = (value, opts = {}) => {
  const { locale = "es-MX", currency = "MXN", fallback = "S/I", minimumFractionDigits = 0, maximumFractionDigits = 0 } = opts;
  const parsed = safeNumber(value);
  if (parsed === null) return fallback;
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits,
    maximumFractionDigits,
  }).format(parsed);
};

export const safePercent = (value, opts = {}) => {
  const { fallback = "S/I", fractionDigits = 2 } = opts;
  const parsed = safeNumber(value);
  if (parsed === null) return fallback;
  return `${parsed.toFixed(fractionDigits)}%`;
};
