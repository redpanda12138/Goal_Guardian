export type SummaryRun = {
  type: "text" | "bold";
  text: string;
};

export type SummaryBlock =
  | {
      type: "paragraph";
      runs: SummaryRun[];
    }
  | {
      type: "list";
      items: SummaryRun[][];
    };

export function parseInline(text: string): SummaryRun[];
export function parseSummaryMarkdown(input: string): SummaryBlock[];

declare const summaryMarkdown: {
  parseInline: typeof parseInline;
  parseSummaryMarkdown: typeof parseSummaryMarkdown;
};

export default summaryMarkdown;
