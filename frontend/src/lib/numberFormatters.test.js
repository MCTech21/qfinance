import { safeCurrency, safeNumber, safePercent } from "./numberFormatters";

describe("numberFormatters", () => {
  test("safeNumber parsea números válidos y regresa null en inválidos", () => {
    expect(safeNumber(10)).toBe(10);
    expect(safeNumber("12.5")).toBe(12.5);
    expect(safeNumber(null)).toBeNull();
    expect(safeNumber("abc")).toBeNull();
  });

  test("safeCurrency no crashea con null", () => {
    expect(safeCurrency(null)).toBe("S/I");
    expect(safeCurrency(0)).toContain("0");
  });

  test("safePercent no crashea con null", () => {
    expect(safePercent(undefined)).toBe("S/I");
    expect(safePercent(0)).toBe("0.00%");
  });
});
