// Page-range parsing for the browser app. Same rules as src/pdfstitch/ranges.py,
// checked against the same cases in tests/range_cases.json.
//
//   5      page 5             3-7    pages 3..7         7-3   pages 7..3
//   4-     page 4 to the end  end    the last page      odd / even
//
// Items are comma-separated and kept in order; an empty spec means all pages.

export class PageSpecError extends Error {}

const ITEM = /^(\d+|end)(?:(-)(\d+|end)?)?$/;

function bound(token, item) {
  if (token === "end") return "end";
  const value = parseInt(token, 10);
  if (value < 1) throw new PageSpecError(`page numbers start at 1, got "${item}"`);
  return value;
}

export function parse(spec) {
  if (spec == null || spec.trim() === "") return [{ start: 1, stop: "end" }];
  return spec.split(",").map((raw) => {
    const item = raw.trim().replace(/\s*-\s*/g, "-").toLowerCase();
    if (item === "") throw new PageSpecError(`empty item in "${spec}"`);
    if (item === "odd" || item === "even") return { parity: item };
    const m = ITEM.exec(item);
    if (!m) throw new PageSpecError(`can't read "${raw.trim()}"`);
    const start = bound(m[1], item);
    const stop = m[2] === undefined ? start : m[3] === undefined ? "end" : bound(m[3], item);
    return { start, stop };
  });
}

export function resolve(items, nPages) {
  if (nPages < 1) throw new PageSpecError("document has no pages");
  const number = (b) => {
    const value = b === "end" ? nPages : b;
    if (value > nPages) {
      throw new PageSpecError(`there is no page ${value}`);
    }
    return value;
  };
  const out = [];
  for (const item of items) {
    if (item.parity) {
      for (let p = item.parity === "odd" ? 1 : 2; p <= nPages; p += 2) out.push(p - 1);
      continue;
    }
    const a = number(item.start);
    const b = number(item.stop);
    const step = b >= a ? 1 : -1;
    for (let p = a; p !== b + step; p += step) out.push(p - 1);
  }
  return out;
}

export const select = (spec, nPages) => resolve(parse(spec), nPages);

export function isSpec(text) {
  if (!text.trim()) return false;
  try {
    parse(text);
    return true;
  } catch {
    return false;
  }
}
