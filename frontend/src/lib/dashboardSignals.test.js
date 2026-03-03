import { percentageLabel, variationClass } from "./dashboardSignals";

test("percentageLabel returns N/A when null", () => {
  expect(percentageLabel(null, "N/A")).toBe("N/A");
});

test("variationClass honors yellow override", () => {
  expect(variationClass({ variacion: -999, variation_color: "yellow" })).toBe("text-yellow-400");
});
