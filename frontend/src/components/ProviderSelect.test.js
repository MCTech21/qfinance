import { render, screen, fireEvent, waitFor } from "@testing-library/react";

jest.useFakeTimers();
import ProviderSelect from "./ProviderSelect";

test("ProviderSelect reorders by relevance and Enter selects highlighted option", async () => {
  const get = jest
    .fn()
    .mockResolvedValueOnce({ data: [] })
    .mockResolvedValueOnce({
      data: [
        { id: "2", name: "Árboles SA" },
        { id: "1", name: "Human", rfc: "RFC1" },
        { id: "3", name: "Servicios Human Capital" },
      ],
    });
  const apiClient = () => ({ get });
  const onChange = jest.fn();
  render(<ProviderSelect apiClient={apiClient} value="" onChange={onChange} />);

  const input = screen.getByPlaceholderText(/Buscar proveedor/i);
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value: "hum" } });

  jest.advanceTimersByTime(260);
  await waitFor(() => expect(get).toHaveBeenCalledWith("/providers", expect.objectContaining({ params: { q: "hum", limit: 20 } })));
  await waitFor(() => {
    const options = screen.getAllByRole("button");
    expect(options[0]).toHaveTextContent(/^Human/);
  });

  fireEvent.keyDown(input, { key: "Enter" });
  expect(onChange).toHaveBeenCalledWith("1", expect.objectContaining({ name: "Human" }));
});
