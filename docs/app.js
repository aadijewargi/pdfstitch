// pdfstitch web app: UI wiring. Merge logic lives in stitch.js.

import { PDFDocument } from "./vendor/pdf-lib.esm.min.js";
import * as pdfjs from "./vendor/pdf.min.mjs";
import { stitch, pagesFor } from "./stitch.js";

pdfjs.GlobalWorkerOptions.workerSrc = new URL("./vendor/pdf.worker.min.mjs", import.meta.url).href;

const $ = (sel) => document.querySelector(sel);
const sheetsEl = $("#sheets");
const template = $("#sheet-template");
const picker = $("#picker");
const stackEl = document.querySelector(".stack");
const mergeBtn = $("#merge");
const statusEl = $("#status");
const totalEl = $("#total");

/** @type {{id:number, name:string, doc:PDFDocument|null, pageCount:number, spec:string, error:string|null, el:HTMLLIElement, bytes:Uint8Array|null}[]} */
let items = [];
let nextId = 1;

// ------------------------------------------------------------------ adding

async function addFiles(fileList) {
  const files = [...fileList].filter((f) => f.type === "application/pdf" || /\.pdf$/i.test(f.name));
  const skipped = fileList.length - files.length;
  if (skipped) setStatus(`Skipped ${skipped} ${skipped === 1 ? "file" : "files"} that ${skipped === 1 ? "isn't a PDF" : "aren't PDFs"}.`, "error");
  else setStatus("");

  const fresh = files.map((file) => {
    const item = { id: nextId++, name: file.name, doc: null, pageCount: 0, spec: "", error: null, el: null, bytes: null };
    item.el = buildSheet(item);
    items.push(item);
    return { item, file };
  });
  render({ added: fresh.map((f) => f.item.id) });

  await Promise.all(
    fresh.map(async ({ item, file }) => {
      try {
        item.bytes = new Uint8Array(await file.arrayBuffer());
        item.doc = await PDFDocument.load(item.bytes, { updateMetadata: false });
        item.pageCount = item.doc.getPageCount();
      } catch (err) {
        item.error = /encrypt/i.test(String(err))
          ? "Password-protected. The browser version can't open these; use the command-line version."
          : "Can't read this file as a PDF.";
      }
      updateSheet(item);
      refresh();
      if (!item.error) drawThumb(item);
    }),
  );
}

async function drawThumb(item) {
  try {
    // pdf.js takes ownership of the buffer it is given, so hand it a copy.
    const task = pdfjs.getDocument({ data: item.bytes.slice(), isEvalSupported: false });
    const pdf = await task.promise;
    const page = await pdf.getPage(1);
    const base = page.getViewport({ scale: 1 });
    const scale = Math.min(128 / base.width, 164 / base.height);
    const viewport = page.getViewport({ scale });
    const canvas = item.el.querySelector("canvas");
    canvas.width = Math.round(viewport.width);
    canvas.height = Math.round(viewport.height);
    canvas.style.width = `${canvas.width / 2}px`;
    canvas.style.height = `${canvas.height / 2}px`;
    await page.render({ canvas, canvasContext: canvas.getContext("2d"), viewport }).promise;
    await pdf.destroy();
  } catch {
    /* a missing thumbnail is not worth bothering anyone about */
  }
}

// ------------------------------------------------------------------ sheets

function buildSheet(item) {
  const el = template.content.firstElementChild.cloneNode(true);
  el.dataset.id = item.id;
  el.querySelector(".name").textContent = item.name;
  el.querySelector(".name").title = item.name;
  el.querySelector(".meta").textContent = "Reading…";
  const input = el.querySelector(".pages input");
  input.setAttribute("aria-label", `Pages to take from ${item.name}`);
  input.addEventListener("input", () => {
    item.spec = input.value;
    updateSheet(item);
    refresh();
  });
  el.querySelector(".up").addEventListener("click", () => move(item, -1));
  el.querySelector(".down").addEventListener("click", () => move(item, +1));
  el.querySelector(".remove").addEventListener("click", () => remove(item));
  wireDrag(el, item);
  return el;
}

function updateSheet(item) {
  const meta = item.el.querySelector(".meta");
  const input = item.el.querySelector(".pages input");
  item.el.classList.toggle("broken", Boolean(item.error));
  meta.classList.remove("error");
  input.removeAttribute("aria-invalid");

  if (item.error) {
    meta.textContent = item.error;
    meta.classList.add("error");
    return;
  }
  if (!item.doc) return;
  const total = `${item.pageCount} ${item.pageCount === 1 ? "page" : "pages"}`;
  try {
    const n = pagesFor(item.spec, item.pageCount);
    meta.textContent = item.spec.trim() ? `${n} of ${total}` : total;
  } catch (err) {
    const msg = err.message.charAt(0).toUpperCase() + err.message.slice(1);
    meta.textContent = `${total}. ${msg}.`;
    meta.classList.add("error");
    input.setAttribute("aria-invalid", "true");
  }
}

function render({ added = [] } = {}) {
  sheetsEl.replaceChildren(...items.map((i) => i.el));
  for (const id of added) {
    const el = sheetsEl.querySelector(`[data-id="${id}"]`);
    el?.classList.add("just-added");
    el?.addEventListener("animationend", () => el.classList.remove("just-added"), { once: true });
  }
  refresh();
}

function refresh() {
  stackEl.classList.toggle("empty", items.length === 0);
  $("#file-count").textContent = items.length ? `(${items.length})` : "";
  $("#sort-name").hidden = items.length < 2;
  $("#clear").hidden = items.length === 0;
  items.forEach((item, i) => {
    item.el.querySelector(".up").disabled = i === 0;
    item.el.querySelector(".down").disabled = i === items.length - 1;
  });

  const ready = items.filter((i) => i.doc && !i.error);
  const loading = items.some((i) => !i.doc && !i.error);
  let pages = 0;
  let bad = 0;
  const duplex = $("#opt-duplex").checked;
  ready.forEach((item, idx) => {
    try {
      const n = pagesFor(item.spec, item.pageCount);
      pages += n + (duplex && idx < ready.length - 1 && n % 2 === 1 ? 1 : 0);
    } catch {
      bad++;
    }
  });

  if (items.length === 0) totalEl.textContent = "Add at least one file to start.";
  else if (bad) totalEl.textContent = `Fix the page ${bad === 1 ? "range" : "ranges"} marked in red.`;
  else if (loading) totalEl.textContent = "Reading files…";
  else if (!ready.length) totalEl.textContent = "None of these files can be merged.";
  else {
    totalEl.innerHTML = "";
    const strong = document.createElement("strong");
    strong.textContent = `${pages} ${pages === 1 ? "page" : "pages"}`;
    totalEl.append(strong, ` from ${ready.length} ${ready.length === 1 ? "file" : "files"}`);
  }
  mergeBtn.disabled = !ready.length || bad > 0 || loading || pages === 0;
}

function move(item, delta) {
  const i = items.indexOf(item);
  const j = i + delta;
  if (j < 0 || j >= items.length) return;
  [items[i], items[j]] = [items[j], items[i]];
  render();
  item.el.querySelector(delta < 0 ? ".up" : ".down").focus();
}

function remove(item) {
  const i = items.indexOf(item);
  items.splice(i, 1);
  render();
  const neighbour = items[Math.min(i, items.length - 1)];
  (neighbour ? neighbour.el.querySelector(".remove") : picker).focus();
}

// ------------------------------------------------------------------ drag to reorder

let dragged = null;

function wireDrag(el, item) {
  el.addEventListener("dragstart", (e) => {
    if (e.target.closest("input, button")) return;
    dragged = item;
    el.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", item.name);
  });
  el.addEventListener("dragend", () => {
    dragged = null;
    el.classList.remove("dragging");
    clearMarkers();
  });
  el.addEventListener("dragover", (e) => {
    if (!dragged || dragged === item) return;
    e.preventDefault();
    clearMarkers();
    el.classList.add(isAfter(e, el) ? "drop-after" : "drop-before");
  });
  el.addEventListener("drop", (e) => {
    if (!dragged || dragged === item) return;
    e.preventDefault();
    e.stopPropagation();
    const after = isAfter(e, el);
    items.splice(items.indexOf(dragged), 1);
    items.splice(items.indexOf(item) + (after ? 1 : 0), 0, dragged);
    clearMarkers();
    render();
  });
}

const isAfter = (e, el) => {
  const box = el.getBoundingClientRect();
  return e.clientY > box.top + box.height / 2;
};
const clearMarkers = () =>
  sheetsEl.querySelectorAll(".drop-before, .drop-after").forEach((n) => n.classList.remove("drop-before", "drop-after"));

// Files dropped anywhere on the page are added.
let fileDepth = 0;
const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes("Files");
window.addEventListener("dragenter", (e) => {
  if (!hasFiles(e)) return;
  fileDepth++;
  document.body.classList.add("file-over");
});
window.addEventListener("dragleave", (e) => {
  if (!hasFiles(e)) return;
  fileDepth = Math.max(0, fileDepth - 1);
  if (!fileDepth) document.body.classList.remove("file-over");
});
window.addEventListener("dragover", (e) => {
  if (hasFiles(e)) e.preventDefault();
});
window.addEventListener("drop", (e) => {
  if (!hasFiles(e)) return;
  e.preventDefault();
  fileDepth = 0;
  document.body.classList.remove("file-over");
  addFiles(e.dataTransfer.files);
});

// ------------------------------------------------------------------ controls

picker.addEventListener("change", () => {
  addFiles(picker.files);
  picker.value = "";
});

$("#sort-name").addEventListener("click", () => {
  const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });
  items.sort((a, b) => collator.compare(a.name, b.name));
  render();
});

$("#clear").addEventListener("click", () => {
  items = [];
  render();
  setStatus("");
  picker.focus();
});

$("#opt-duplex").addEventListener("change", refresh);

function outputName() {
  let name = $("#out-name").value.trim().replace(/[\\/:*?"<>|]+/g, "-") || "merged.pdf";
  if (!/\.pdf$/i.test(name)) name += ".pdf";
  return name;
}

function setStatus(text, kind = "") {
  statusEl.textContent = text;
  statusEl.className = `status ${kind}`;
}

mergeBtn.addEventListener("click", async () => {
  const parts = items
    .filter((i) => i.doc && !i.error)
    .map((i) => ({ doc: i.doc, spec: i.spec, label: i.name.replace(/\.pdf$/i, "") }));
  mergeBtn.disabled = true;
  setStatus("Merging…");
  try {
    const name = outputName();
    const { bytes, pageCount } = await stitch(parts, {
      bookmarks: $("#opt-bookmarks").checked,
      duplex: $("#opt-duplex").checked,
      title: name.replace(/\.pdf$/i, ""),
    });
    const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: name });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
    const size = bytes.length > 1e6 ? `${(bytes.length / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes.length / 1e3))} KB`;
    setStatus(`Downloaded ${name}: ${pageCount} ${pageCount === 1 ? "page" : "pages"}, ${size}.`, "ok");
  } catch (err) {
    setStatus(`Couldn't merge: ${err.message}`, "error");
  } finally {
    refresh();
  }
});

refresh();
