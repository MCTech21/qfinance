import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ProviderSelect from "./ProviderSelect";

test("ProviderSelect loads and filters providers", async () => {
  const apiClient = () => ({
    get: jest.fn().mockResolvedValue({ data: [{ id: "1", name: "Alpha" }, { id: "2", name: "Beta" }] }),
  });
  const onChange = jest.fn();
  render(<ProviderSelect apiClient={apiClient} value="" onChange={onChange} />);
  fireEvent.change(screen.getByPlaceholderText(/Buscar proveedor/i), { target: { value: "a" } });
  await waitFor(() => expect(screen.getByText("Alpha")).toBeInTheDocument());
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "1" } });
  expect(onChange).toHaveBeenCalledWith("1");
});
