import { render, screen, waitFor } from "@testing-library/react";
import Dashboard from "./Dashboard";

const mockGet = jest.fn();

jest.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    api: () => ({ get: mockGet }),
    allowedCompanies: [{ id: "c1" }],
    user: { role: "admin" },
  }),
}));

jest.mock("sonner", () => ({ toast: { error: jest.fn() } }));

describe("Dashboard", () => {
  beforeEach(() => {
    mockGet.mockReset();
  });

  test("renderiza KPIs y tabla P&L con subtotales", async () => {
    mockGet
      .mockResolvedValueOnce({ data: {
        filtros: { period_label: "2026-01" },
        totals: { ingreso_proyectado_405: 1000, presupuesto_total: 500, ejecutado_total: 200, por_ejercer_total: 300, traffic_light: "green", ejecucion_vs_ingreso_pct: 20 },
        rows: [
          { code: "101", name: "TERRENO", budget: 100, real: 50, remaining: 50, income_pct: 5, traffic_light: "green", row_type: "partida" },
          { code: "SUBTOTAL_GROSS", name: "UTILIDAD BRUTA", budget: 900, real: 950, remaining: -50, income_pct: 95, traffic_light: "green", row_type: "subtotal" },
        ],
      }})
      .mockResolvedValueOnce({ data: [{ id: "c1", nombre: "Empresa" }] })
      .mockResolvedValueOnce({ data: [{ id: "p1", empresa_id: "c1", name: "Proyecto" }] });

    render(<Dashboard />);

    await waitFor(() => expect(screen.getByTestId("kpi-grid")).toBeInTheDocument());
    expect(screen.getByText(/Ingreso proyectado 405/i)).toBeInTheDocument();
    expect(screen.getByTestId("pl-table")).toBeInTheDocument();
    expect(screen.getByText(/UTILIDAD BRUTA/i)).toBeInTheDocument();
  });

  test("muestra empty state", async () => {
    mockGet
      .mockResolvedValueOnce({ data: { filtros: { period_label: "2026" }, totals: {}, rows: [] } })
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: [] });

    render(<Dashboard />);

    await waitFor(() => expect(screen.getByTestId("empty-state")).toBeInTheDocument());
  });
});
