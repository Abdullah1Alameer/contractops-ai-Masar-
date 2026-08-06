/** @vitest-environment jsdom */
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import NegotiationMonitorRedirect from "@/app/negotiations/monitor/page";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

afterEach(cleanup);

describe("Old /negotiations/monitor route (Bug 3 backward-compatible redirect)", () => {
  it("redirects any old link/bookmark straight to the unified /negotiations page", () => {
    render(<NegotiationMonitorRedirect />);

    expect(replace).toHaveBeenCalledWith("/negotiations");
  });
});
