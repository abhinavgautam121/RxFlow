import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Rate, Table } from "./common";
describe("Operational evidence components", () => {
  it("shows the numerator and denominator behind a rate", () => {
    render(<Rate value={75} n={3} d={4} />);
    expect(screen.getByText("75%")).toBeInTheDocument();
    expect(screen.getByText("3 / 4")).toBeInTheDocument();
  });
  it("searches, sorts and paginates a record table", () => {
    render(
      <Table
        rows={[
          { name: "Bengaluru", orders: 20 },
          { name: "Delhi", orders: 10 },
          { name: "Mumbai", orders: 30 },
        ]}
        columns={[
          { key: "name", label: "City" },
          { key: "orders", label: "Orders" },
        ]}
        pageSize={2}
      />,
    );
    expect(screen.queryByText("Mumbai")).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Next page"));
    expect(screen.getByText("Mumbai")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Search table"), {
      target: { value: "Delhi" },
    });
    expect(screen.getByText("Delhi")).toBeInTheDocument();
    expect(screen.queryByText("Mumbai")).not.toBeInTheDocument();
  });
  it("reports an empty filtered population", () => {
    render(<Table rows={[]} columns={[{ key: "name", label: "Name" }]} />);
    expect(
      screen.getByText("No records match these filters."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Next page")).toBeDisabled();
  });
});
