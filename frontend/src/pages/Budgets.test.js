import { render, screen, waitFor } from "@testing-library/react";
import Budgets from "./Budgets";

const mockGet = jest.fn();

jest.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    api: () => ({ get: mockGet, post: jest.fn(), put: jest.fn(), delete: jest.fn() }),
    canManage: true,
    user: { role: "admin" },
  }),
}));

jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));

describe("Budgets", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockGet.mockImplementation((url) => {
      if (url === "/budgets") {
        return Promise.resolve({
          data: [
            { id: "b1", project_id: "p1", partida_codigo: "101", total_amount: "1200" },
            { id: "b2", project_id: "p2", partida_codigo: "202", total_amount: "800" },
          ],
        });
      }
      if (url === "/projects") {
        return Promise.resolve({ data: [{ id: "p1", empresa_id: "c1", name: "Proyecto 1" }, { id: "p2", empresa_id: "c2", name: "Proyecto 2" }] });
      }
      if (url === "/catalogo-partidas") {
        return Promise.resolve({ data: [{ codigo: "101", nombre: "Terreno" }, { codigo: "202", nombre: "Material" }] });
      }
      if (url === "/empresas") {
        return Promise.resolve({ data: [{ id: "c1", nombre: "Empresa 1" }, { id: "c2", nombre: "Empresa 2" }] });
      }
      if (url === "/budget-requests") {
        return Promise.resolve({ data: [] });
      }
      return Promise.resolve({ data: [] });
    });
  });

  test("tabla no muestra partida N/A cuando backend entrega partidas válidas", async () => {
    render(<Budgets />);
    await waitFor(() => expect(screen.getByTestId("budgets-table")).toBeInTheDocument());
    expect(screen.queryByText("N/A")).not.toBeInTheDocument();
  });

  test("filtro inicial de proyecto envía all y no mezcla por default", async () => {
    render(<Budgets />);
    await waitFor(() => expect(screen.getByTestId("budgets-table")).toBeInTheDocument());
    const budgetsCall = mockGet.mock.calls.find((call) => call[0] === "/budgets");
    expect(budgetsCall[1].params.project_id).toBeUndefined();
  });
});
