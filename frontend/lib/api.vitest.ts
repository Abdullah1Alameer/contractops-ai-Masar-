import { describe, expect, it } from "vitest";

import { ApiError, apiErrorCode } from "@/lib/api";


describe("apiErrorCode", () => {
  it("returns the deterministic backend error code", () => {
    expect(apiErrorCode(new ApiError(409, "review_closed"))).toBe("review_closed");
  });

  it("uses the fallback for non-API failures", () => {
    expect(apiErrorCode(new Error("network failed"), "unknown_error")).toBe("unknown_error");
  });
});
