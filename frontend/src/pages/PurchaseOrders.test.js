import { calcIvaWithholdingAmount, calcLine } from "./purchaseOrderTaxes";

describe("PurchaseOrders IVA withholding helpers", () => {
  test("calcula retención IVA solo cuando está activa y con tasa válida", () => {
    expect(calcIvaWithholdingAmount(160, false, "10")).toBe(0);
    expect(calcIvaWithholdingAmount(160, true, "0")).toBe(0);
    expect(calcIvaWithholdingAmount(160, true, "10")).toBe(16);
  });

  test("total de OC descuenta Ret IVA y mantiene compatibilidad con Ret ISR", () => {
    const line = calcLine({
      qty: "1",
      price_unit: "100",
      discount_pct: "0",
      iva_rate: "16",
      apply_isr_withholding: true,
      isr_withholding_rate: "10",
    });

    const ivaWithholding = calcIvaWithholdingAmount(line.ivaAmount, true, "10");
    const total = Number((line.taxableBase + line.ivaAmount - line.isrAmount - ivaWithholding).toFixed(2));

    expect(line.taxableBase).toBe(100);
    expect(line.ivaAmount).toBe(16);
    expect(line.isrAmount).toBe(10);
    expect(ivaWithholding).toBe(1.6);
    expect(total).toBe(104.4);
  });
});
