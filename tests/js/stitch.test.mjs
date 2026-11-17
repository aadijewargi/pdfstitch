// Tests the browser app's merge logic in Node, with the same vendored pdf-lib
// the page uses. Each test page has a distinct width, so output order can be
// read back page by page. Usage: node --test tests/js/stitch.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { PDFDocument, PDFName, PDFDict, PDFRef } from "../../docs/vendor/pdf-lib.esm.min.js";
import { stitch } from "../../docs/stitch.js";

async function makeDoc(widths) {
  const doc = await PDFDocument.create();
  for (const w of widths) doc.addPage([w, 500]);
  return PDFDocument.load(await doc.save());
}

async function widthsOf(bytes) {
  const doc = await PDFDocument.load(bytes);
  return doc.getPages().map((p) => Math.round(p.getWidth()));
}

async function outlineOf(bytes) {
  const doc = await PDFDocument.load(bytes);
  const ctx = doc.context;
  if (!doc.catalog.has(PDFName.of("Outlines"))) return [];
  const root = doc.catalog.lookup(PDFName.of("Outlines"), PDFDict);
  const pageRefs = doc.getPages().map((p) => p.ref.toString());
  const out = [];
  let ref = root.get(PDFName.of("First"));
  while (ref instanceof PDFRef) {
    const item = ctx.lookup(ref, PDFDict);
    const title = item.lookup(PDFName.of("Title")).decodeText();
    const dest = item.lookup(PDFName.of("Dest"));
    out.push([title, pageRefs.indexOf(dest.get(0).toString())]);
    ref = item.get(PDFName.of("Next"));
  }
  assert.equal(root.lookup(PDFName.of("Count")).asNumber(), out.length);
  return out;
}

test("files and page ranges in order", async () => {
  const a = await makeDoc([101, 102, 103]);
  const b = await makeDoc([201, 202]);
  const { bytes, pageCount } = await stitch([
    { doc: a, spec: "", label: "a" },
    { doc: b, spec: "end-1", label: "b" },
    { doc: a, spec: "3,1,1", label: "a again" },
  ]);
  assert.equal(pageCount, 8);
  assert.deepEqual(await widthsOf(bytes), [101, 102, 103, 202, 201, 103, 101, 101]);
});

test("bookmarks point at each file's first page, with non-ASCII titles", async () => {
  const a = await makeDoc([101, 102]);
  const b = await makeDoc([201]);
  const { bytes } = await stitch([
    { doc: a, label: "Résumé" },
    { doc: b, label: "第二章" },
  ]);
  assert.deepEqual(await outlineOf(bytes), [["Résumé", 0], ["第二章", 2]]);
  const doc = await PDFDocument.load(bytes);
  assert.equal(doc.catalog.get(PDFName.of("PageMode")).toString(), "/UseOutlines");
});

test("no bookmarks when turned off", async () => {
  const a = await makeDoc([101]);
  const { bytes } = await stitch([{ doc: a, label: "a" }], { bookmarks: false });
  assert.deepEqual(await outlineOf(bytes), []);
});

test("duplex pads odd parts except the last", async () => {
  const a = await makeDoc([101, 102, 103]);
  const b = await makeDoc([201]);
  const c = await makeDoc([301]);
  const { bytes } = await stitch(
    [{ doc: a, label: "a" }, { doc: b, label: "b" }, { doc: c, label: "c" }],
    { duplex: true },
  );
  assert.deepEqual(await widthsOf(bytes), [101, 102, 103, 103, 201, 201, 301]);
  assert.deepEqual(await outlineOf(bytes), [["a", 0], ["b", 4], ["c", 6]]);
});

test("title metadata", async () => {
  const a = await makeDoc([101]);
  const { bytes } = await stitch([{ doc: a, label: "a" }], { title: "Report" });
  assert.equal((await PDFDocument.load(bytes)).getTitle(), "Report");
});

test("bad range and empty input are rejected", async () => {
  const a = await makeDoc([101]);
  await assert.rejects(stitch([{ doc: a, spec: "2", label: "a" }]), /no page 2/);
  await assert.rejects(stitch([]), /no files/);
  await assert.rejects(stitch([{ doc: a, spec: "even", label: "a" }]), /empty/);
});
