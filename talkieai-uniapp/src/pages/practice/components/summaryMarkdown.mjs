function pushParagraph(blocks, lines) {
  if (!lines.length) return;
  const text = lines.join("\n").trim();
  if (!text) return;
  blocks.push({
    type: "paragraph",
    runs: parseInline(text),
  });
}

function pushList(blocks, items) {
  if (!items.length) return;
  blocks.push({
    type: "list",
    items: items.map((item) => parseInline(item)),
  });
}

export function parseInline(text) {
  const value = typeof text === "string" ? text : "";
  if (!value) return [];

  const runs = [];
  let index = 0;

  while (index < value.length) {
    const match = value
      .slice(index)
      .match(/(\*\*[^*]+\*\*|__[^_]+__|\*[^*\n]+\*|_[^_\n]+_)/);

    if (!match || match.index == null) {
      runs.push({ type: "text", text: value.slice(index) });
      break;
    }

    const matchStart = index + match.index;
    if (matchStart > index) {
      runs.push({ type: "text", text: value.slice(index, matchStart) });
    }

    const token = match[0];
    const markerLength = token.startsWith("**") || token.startsWith("__") ? 2 : 1;
    const inner = token.slice(markerLength, token.length - markerLength);
    runs.push({ type: "bold", text: inner });
    index = matchStart + token.length;
  }

  return runs.filter((run) => run.text);
}

export function parseSummaryMarkdown(input) {
  const text = typeof input === "string" ? input.replace(/\r\n?/g, "\n") : "";
  if (!text.trim()) return [];

  const blocks = [];
  const paragraphLines = [];
  const listItems = [];

  const flushParagraph = () => {
    pushParagraph(blocks, paragraphLines);
    paragraphLines.length = 0;
  };

  const flushList = () => {
    pushList(blocks, listItems);
    listItems.length = 0;
  };

  text.split("\n").forEach((line) => {
    const trimmed = line.trim();
    const bulletMatch = trimmed.match(/^([*-])\s+(.+)$/);

    if (!trimmed) {
      flushParagraph();
      flushList();
      return;
    }

    if (bulletMatch) {
      flushParagraph();
      listItems.push(bulletMatch[2].trim());
      return;
    }

    flushList();
    paragraphLines.push(trimmed);
  });

  flushParagraph();
  flushList();

  return blocks;
}

const summaryMarkdown = {
  parseInline,
  parseSummaryMarkdown,
};

export default summaryMarkdown;
