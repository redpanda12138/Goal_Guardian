test("parses bold text and bullet lines into blocks", async () => {
  const { parseSummaryMarkdown } = await import("./summaryMarkdown.mjs");
  const blocks = parseSummaryMarkdown(
    "**Focus** on hydration\n* Drink water\n* Walk 20 minutes"
  );

  expect(blocks).toEqual([
    {
      type: "paragraph",
      runs: [
        { type: "bold", text: "Focus" },
        { type: "text", text: " on hydration" },
      ],
    },
    {
      type: "list",
      items: [
        [{ type: "text", text: "Drink water" }],
        [{ type: "text", text: "Walk 20 minutes" }],
      ],
    },
  ]);
});
