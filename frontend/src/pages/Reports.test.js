import { render, screen, waitFor } from "@testing-library/react";
import Reports from "./Reports";

const mockGet = jest.fn();

jest.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    api: () => ({ get: mockGet, post: jest.fn() }),
  }),
}));

jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));

describe("Reports", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockGet.mockImplementation((url) => {
      if (url === "/empresas") return Promise.resolve({ data: [{ id: "c1", nombre: "Empresa" }] });
      if (url === "/projects") return Promise.resolve({ data: [{ id: "p1", empresa_id: "c1", name: "Proyecto" }] });
      if (url === "/reports/export-data") return Promise.resolve({ data: { filtros: { empresa: "Todas", proyecto: "Todos" }, periodo: "Enero 2026", generated_at: "", timezone: "America/Tijuana", resumen: { presupuesto: 0, ejecutado: 0, variacion: 0, porcentaje: 0, semaforo: "Normal" }, detalle_partidas: [] } });
      return Promise.resolve({ data: {} });
    });
  });

  test("no carga dashboard al montar reportes", async () => {
    render(<Reports />);

    await waitFor(() => expect(screen.getByTestId("reports-page")).toBeInTheDocument());
    expect(mockGet).toHaveBeenCalledWith("/empresas");
    expect(mockGet).toHaveBeenCalledWith("/projects");
    expect(mockGet).not.toHaveBeenCalledWith("/reports/dashboard", expect.anything());
  });
});
