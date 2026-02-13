export const getYearRange = () => {
  const currentYear = new Date().getFullYear();
  const fromYear = Math.min(2025, currentYear);
  const toYear = Math.max(currentYear + 10, 2031);
  return { fromYear, toYear };
};

export const buildYearOptions = () => {
  const { fromYear, toYear } = getYearRange();
  return Array.from({ length: toYear - fromYear + 1 }, (_, i) => fromYear + i);
};
