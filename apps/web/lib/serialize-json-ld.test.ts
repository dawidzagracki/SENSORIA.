import { describe, expect, it } from "vitest";
import { serializeJsonLd } from "./serialize-json-ld";

describe("JSON-LD serialization", () => {
  it("escapes script terminators and preserves valid JSON data", () => {
    const serialized = serializeJsonLd({
      name: "Świadoma </script><script>alert(1)</script>",
    });

    expect(serialized).not.toContain("</script>");
    expect(serialized).toContain("\\u003c/script\\u003e");
    expect(JSON.parse(serialized)).toEqual({
      name: "Świadoma </script><script>alert(1)</script>",
    });
  });
});
