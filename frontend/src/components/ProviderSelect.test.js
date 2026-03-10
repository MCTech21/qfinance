import { render, screen, fireEvent, waitFor } from "@testing-library/react";

jest.useFakeTimers();
import ProviderSelect from "./ProviderSelect";

test("ProviderSelect supports typeahead and keyboard selection", async () => {
  const get = jest.fn().mockResolvedValue({ data: [{ id: "1", name: "CEMEX", rfc: "RFC1" }, { id: "2", name: "Beta" }] });
  const apiClient = () => ({ get });
  const onChange = jest.fn();
  render(<ProviderSelect apiClient={apiClient} value="" onChange={onChange} />);

  const input = screen.getByPlaceholderText(/Buscar proveedor/i);
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value: "C" } });

  jest.advanceTimersByTime(260);
  await waitFor(() => expect(get).toHaveBeenCalledWith("/providers", expect.objectContaining({ params: { q: "C", limit: 20 } })));
  await waitFor(() => expect(screen.getByText(/CEMEX/i)).toBeInTheDocument());
  fireEvent.keyDown(input, { key: "ArrowDown" });
  fireEvent.keyDown(input, { key: "Enter" });
  expect(onChange).toHaveBeenCalledWith("1", expect.objectContaining({ name: "CEMEX" }));
});
