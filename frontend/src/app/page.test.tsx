import React from "react";
import { render, screen } from "@testing-library/react";
import Home from "./page";

describe("Home", () => {
  it("renders the baseline app shell", () => {
    render(<Home />);

    expect(
      screen.getByRole("heading", {
        name: "Campaign analytics for brand visibility in AI answers"
      })
    ).toBeInTheDocument();
    expect(screen.getByText("FastAPI backend")).toBeInTheDocument();
  });
});
