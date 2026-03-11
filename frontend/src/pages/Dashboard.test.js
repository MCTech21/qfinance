import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

const baseDashboardPayload = {
  filtros: { period_label: "2026-01", empresa_nombre: "Empresa", project_nombre: "Proyecto" },
  totals: { ingreso_proyectado_405: 1000, presupuesto_total: 500, ejecutado_total: 200, por_ejercer_total: 300, traffic_light: "green", ejecucion_vs_ingreso_pct: 20 },
  shared_kpis: { ingreso_proyectado_405: 1000, presupuesto_total: 500, real_ejecutado: 200, por_ejercer: 300, ejecucion_vs_ingreso_pct: 20 },
  pnl: {
    rows: [
      { code: "101", name: "TERRENO", budget: 100, real: 50, remaining: 50, income_pct: 5, traffic_light: "green", row_type: "partida" },
      { code: "SUBTOTAL_GROSS", name: "UTILIDAD BRUTA", budget: 900, real: 950, remaining: -50, income_pct: 95, traffic_light: "green", row_type: "subtotal" },
    ],
  },
  budget_control: {
    summary: { red_count: 1, yellow_count: 1, overrun_count: 1, committed_total: 60, available_total: 40 },
    rows: [
      { code: "101", name: "TERRENO", group: "COSTOS DIRECTOS", budget: 100, real: 50, committed: 40, available: 10, advance_pct: 50, traffic_light: "green" },
    ],
  },
  financial_projection: {
    kpis: {
      projected_income_remaining: 800,
      pending_expense_remaining: 240,
      projected_net_flow: 220,
      projected_final_balance: 120,
      max_funding_need: 90,
      critical_cash_period: "2026-03",
    },
    assumptions: ["Escenario base del sistema."],
    rows: [
      {
        period_label: "2026-01",
        opening_balance: 0,
        realized_income: 100,
        projected_income: 200,
        realized_expense: 50,
        committed_expense: 20,
        pending_budget_expense: 10,
        net_flow: 220,
        closing_balance: 220,
        funding_required: 0,
        traffic_light: "green",
      },
    ],
  },
};

describe("Dashboard", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockGet.mockImplementation((url) => {
      if (url === "/reports/dashboard") return Promise.resolve({ data: baseDashboardPayload });
      if (url === "/empresas") return Promise.resolve({ data: [{ id: "c1", nombre: "Empresa" }] });
      if (url === "/projects") return Promise.resolve({ data: [{ id: "p1", empresa_id: "c1", name: "Proyecto" }] });
      return Promise.resolve({ data: {} });
    });
  });

  test("renderiza tabs, globales y navega entre P&L y Control Presupuestal", async () => {
    render(<Dashboard />);

    await waitFor(() => expect(screen.getByTestId("kpi-grid")).toBeInTheDocument());
    expect(screen.getByRole("tab", { name: "P&L" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Control Presupuestal" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Proyección Financiera" })).toBeInTheDocument();
    expect(screen.getByTestId("pl-table")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: "Control Presupuestal" }));
    expect(screen.getByTestId("budget-control-table")).toBeInTheDocument();
    expect(screen.getByText(/Comprometido total/i)).toBeInTheDocument();
    expect(screen.getByTestId("kpi-grid")).toBeInTheDocument();
  });

  test("renderiza Proyección Financiera con KPIs y tabla", async () => {
    render(<Dashboard />);

    await waitFor(() => expect(screen.getByRole("tab", { name: "Proyección Financiera" })).toBeInTheDocument());
    await userEvent.click(screen.getByRole("tab", { name: "Proyección Financiera" }));
    expect(screen.getByTestId("projection-table")).toBeInTheDocument();
    expect(screen.getByTestId("projection-assumptions")).toBeInTheDocument();
    expect(screen.getByTestId("critical-period")).toHaveTextContent("2026-03");
  });

  test("muestra empty state en P&L y control", async () => {
    mockGet.mockImplementation((url) => {
      if (url === "/reports/dashboard") return Promise.resolve({ data: { filtros: { period_label: "2026" }, totals: {}, shared_kpis: {}, pnl: { rows: [] }, budget_control: { rows: [], summary: {} }, financial_projection: { rows: [], kpis: {}, assumptions: [] } } });
      if (url === "/empresas") return Promise.resolve({ data: [] });
      if (url === "/projects") return Promise.resolve({ data: [] });
      return Promise.resolve({ data: {} });
    });

    render(<Dashboard />);

    await waitFor(() => expect(screen.getByTestId("empty-state")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("tab", { name: "Control Presupuestal" }));
    expect(screen.getByTestId("budget-control-empty")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Proyección Financiera" }));
    expect(screen.getByTestId("projection-empty")).toBeInTheDocument();
  });

  test("inicializa en TODO y no envía month/quarter para period=all", async () => {
    render(<Dashboard />);

    await waitFor(() => expect(screen.getByTestId("kpi-grid")).toBeInTheDocument());
    expect(mockGet).toHaveBeenCalledWith("/reports/dashboard", {
      params: expect.objectContaining({
        empresa_id: "all",
        project_id: "all",
        period: "all",
      }),
    });

    const dashboardCall = mockGet.mock.calls.find((call) => call[0] === "/reports/dashboard");
    expect(dashboardCall[1].params.month).toBeUndefined();
    expect(dashboardCall[1].params.quarter).toBeUndefined();
  });
});
