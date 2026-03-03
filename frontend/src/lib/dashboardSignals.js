export const variationClass = (row) => {
  if (row?.variation_color === "yellow") return "text-yellow-400";
  return (Number(row?.variacion || 0) >= 0) ? "text-emerald-400" : "text-red-400";
};

export const percentageLabel = (pct, fallback) => {
  if (pct === null || pct === undefined) return fallback || "N/A";
  return `${Number(pct).toFixed(1)}%`;
};
