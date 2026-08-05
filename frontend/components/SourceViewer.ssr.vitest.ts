/** @vitest-environment node */
import { describe, expect, it } from "vitest";

describe("SourceViewer server import", () => {
  it("does not evaluate browser-only PDF.js globals during server import", async () => {
    await expect(import("@/components/SourceViewer")).resolves.toHaveProperty("default");
  });

  it("allows the Flowdown page module graph to load without browser globals", async () => {
    await expect(import("@/app/flowdown/page")).resolves.toHaveProperty("default");
  });
});
