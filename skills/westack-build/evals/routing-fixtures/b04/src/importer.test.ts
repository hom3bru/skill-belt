import { describe, expect, it } from "vitest";
import { parseCsv } from "./importer";

describe("parseCsv", () => {
  it("reads a header and rows", () => {
    const rows = parseCsv("id,name,amount\n1,Ada,12.5\n2,Grace,7\n");
    expect(rows).toEqual([
      { id: "1", name: "Ada", amount: 12.5 },
      { id: "2", name: "Grace", amount: 7 },
    ]);
  });
});
