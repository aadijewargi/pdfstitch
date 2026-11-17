// The browser app's merge logic, kept free of DOM code so it can be tested in
// Node (tests/js/stitch.test.mjs) as well as run in the page.

import { PDFDocument, PDFName, PDFHexString } from "./vendor/pdf-lib.esm.min.js";
import { select } from "./ranges.js";

/**
 * Merge parts into one PDF.
 * @param {{doc: PDFDocument, spec?: string, label: string}[]} parts
 * @param {{bookmarks?: boolean, duplex?: boolean, title?: string}} options
 * @returns {Promise<{bytes: Uint8Array, pageCount: number}>}
 */
export async function stitch(parts, { bookmarks = true, duplex = false, title } = {}) {
  if (parts.length === 0) throw new Error("no files to merge");
  const out = await PDFDocument.create();
  const marks = [];

  for (let i = 0; i < parts.length; i++) {
    const { doc, spec, label } = parts[i];
    const indices = select(spec, doc.getPageCount());
    const start = out.getPageCount();
    const copied = await out.copyPages(doc, indices);
    for (const page of copied) out.addPage(page);
    if (indices.length > 0) marks.push({ title: label, pageIndex: start });

    const added = out.getPageCount() - start;
    const isLast = i === parts.length - 1;
    if (duplex && !isLast && added % 2 === 1) {
      const { width, height } = out.getPage(out.getPageCount() - 1).getSize();
      out.addPage([width, height]);
    }
  }

  if (out.getPageCount() === 0) throw new Error("the page selections are all empty");
  if (bookmarks && marks.length) addOutline(out, marks);
  if (title) out.setTitle(title);
  out.setProducer("pdfstitch (pdf-lib)");
  out.setCreator("pdfstitch web app");

  const bytes = await out.save();
  return { bytes, pageCount: out.getPageCount() };
}

/** Pages a part will contribute, or throws PageSpecError. */
export const pagesFor = (spec, pageCount) => select(spec, pageCount).length;

/**
 * pdf-lib has no bookmark API, so build a flat /Outlines tree by hand
 * (PDF 1.7 spec, section 12.3.3): one item per file, linked as a doubly
 * linked list under the outline root, each jumping to its first page.
 */
export function addOutline(doc, entries) {
  const ctx = doc.context;
  const pages = doc.getPages();
  const root = ctx.nextRef();
  const refs = entries.map(() => ctx.nextRef());

  entries.forEach((entry, i) => {
    const item = ctx.obj({
      Title: PDFHexString.fromText(entry.title),
      Parent: root,
      Dest: [pages[entry.pageIndex].ref, "Fit"],
    });
    if (i > 0) item.set(PDFName.of("Prev"), refs[i - 1]);
    if (i < refs.length - 1) item.set(PDFName.of("Next"), refs[i + 1]);
    ctx.assign(refs[i], item);
  });

  ctx.assign(root, ctx.obj({ Type: "Outlines", First: refs[0], Last: refs[refs.length - 1], Count: refs.length }));
  doc.catalog.set(PDFName.of("Outlines"), root);
  doc.catalog.set(PDFName.of("PageMode"), PDFName.of("UseOutlines"));
}
