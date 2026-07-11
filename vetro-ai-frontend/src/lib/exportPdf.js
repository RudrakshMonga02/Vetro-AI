// Client-side PDF export of a conversation -- "save locally," no server
// round-trip, no Catalyst SmartBrowz dependency.
//
// Renders real, selectable/searchable text via jsPDF, walking each
// assistant message's markdown AST (parsed with remark, the same
// GFM-enabled parser MarkdownMessage.jsx uses on screen) rather than
// screenshotting the rendered DOM. An earlier version used
// html2canvas to screenshot the chat panel -- simpler, but the result
// was a picture: no selectable/searchable text, no real links, and a
// much larger file for long conversations. Real text also means a
// future "clickable citation" feature (e.g. [Source: FIR #412/2025])
// can stay a genuine clickable link in the exported PDF, not just
// styled pixels.
// Dynamically imported in exportConversationToPdf() and cached here --
// keeps this (fairly heavy) toolchain out of the initial page bundle,
// only loaded the first time a user actually clicks Export PDF.
let jsPDFCtor = null;
let markdownParser = null;
let mdastToString = null;

// jsPDF's built-in core fonts (Helvetica/Courier) only support WinAnsi
// encoding -- Kannada script (or any non-Latin script) silently comes
// out as mangled/garbage glyphs, not an error. Embedding a real Unicode
// font (Noto Sans Kannada, OFL-1.1, files in public/fonts/) is the only
// fix. Fetched once and cached as base64 -- these are ~115KB each, not
// worth re-fetching per export.
const KANNADA_FONT_FAMILY = "NotoSansKannada";
// U+0C80-U+0CFF: the Unicode "Kannada" block. Escaped explicitly
// (rather than pasting the literal glyphs) so the range is
// unambiguous regardless of how this file's encoding gets handled.
const KANNADA_RANGE_RE = /[\u0C80-\u0CFF]/;
let kannadaFontsPromise = null;

function containsKannada(text) {
  return KANNADA_RANGE_RE.test(text || "");
}

function arrayBufferToBase64(buffer) {
  let binary = "";
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}

async function loadKannadaFonts() {
  if (!kannadaFontsPromise) {
    kannadaFontsPromise = Promise.all([
      fetch("/fonts/NotoSansKannada-Regular.ttf").then((r) => r.arrayBuffer()),
      fetch("/fonts/NotoSansKannada-Bold.ttf").then((r) => r.arrayBuffer()),
    ]).then(([regular, bold]) => ({
      regular: arrayBufferToBase64(regular),
      bold: arrayBufferToBase64(bold),
    }));
  }
  return kannadaFontsPromise;
}

// Registered per jsPDF document instance -- addFileToVFS()/addFont()
// are instance-scoped, not global, so this needs to run once per
// exportConversationToPdf() call rather than once per module load.
async function registerKannadaFont(doc) {
  const fonts = await loadKannadaFonts();
  doc.addFileToVFS("NotoSansKannada-Regular.ttf", fonts.regular);
  doc.addFont("NotoSansKannada-Regular.ttf", KANNADA_FONT_FAMILY, "normal");
  doc.addFileToVFS("NotoSansKannada-Bold.ttf", fonts.bold);
  doc.addFont("NotoSansKannada-Bold.ttf", KANNADA_FONT_FAMILY, "bold");
}

async function ensureLibsLoaded() {
  if (jsPDFCtor) return;
  const [{ jsPDF }, { unified }, { default: remarkParse }, { default: remarkGfm }, mdastUtil] =
    await Promise.all([
      import("jspdf"),
      import("unified"),
      import("remark-parse"),
      import("remark-gfm"),
      import("mdast-util-to-string"),
    ]);
  jsPDFCtor = jsPDF;
  markdownParser = unified().use(remarkParse).use(remarkGfm);
  mdastToString = mdastUtil.toString;
}

const PAGE_WIDTH = 210;
const PAGE_HEIGHT = 297;
const MARGIN_X = 16;
const MARGIN_TOP = 18;
const MARGIN_BOTTOM = 18;
const CONTENT_WIDTH = PAGE_WIDTH - MARGIN_X * 2;

// Same brand palette as the app's "incident log" theme, darkened where
// needed for contrast against a printable white page instead of the
// on-screen dark background.
const COLOR = {
  heading: [150, 105, 14], // dark amber
  body: [30, 36, 51],
  muted: [107, 116, 136],
  queryBar: [42, 51, 72],
  resultBar: [58, 107, 76],
  errorBar: [176, 80, 60],
  code: [58, 63, 76],
  codeBg: [240, 241, 245],
  blockquote: [85, 96, 110],
  rule: [222, 224, 230],
  tableHeaderBg: [240, 241, 245],
  tableBorder: [210, 213, 220],
};

function sanitizeFilename(title) {
  const base = (title || "conversation")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  const date = new Date().toISOString().slice(0, 10);
  return `${base || "conversation"}-${date}.pdf`;
}

// --- Low-level page/cursor helpers -----------------------------------

function newCursor(doc) {
  return { doc, y: MARGIN_TOP };
}

function ensureSpace(cursor, height) {
  if (cursor.y + height > PAGE_HEIGHT - MARGIN_BOTTOM) {
    cursor.doc.addPage();
    cursor.y = MARGIN_TOP;
  }
}

function hr(cursor) {
  ensureSpace(cursor, 4);
  cursor.doc.setDrawColor(...COLOR.rule);
  cursor.doc.line(MARGIN_X, cursor.y, PAGE_WIDTH - MARGIN_X, cursor.y);
  cursor.y += 4;
}

// Draws a vertical accent bar (like the app's border-l-2) alongside
// whatever content is printed between `startY` and the cursor's
// current y once the caller is done.
function verticalBar(doc, x, startY, endY, color) {
  if (endY <= startY) return;
  doc.setDrawColor(...color);
  doc.setLineWidth(0.8);
  doc.line(x, startY, x, endY);
}

// --- Rich-text (inline markdown) word wrapping -----------------------

// Flattens a paragraph/heading's inline mdast children into a flat
// list of styled "words" (jsPDF has no native mixed-style text-wrap,
// so this does it manually: measure each word in its own font, wrap
// greedily, print word-by-word).
function inlineToWords(nodes, style = {}) {
  const words = [];
  for (const node of nodes || []) {
    switch (node.type) {
      case "text":
        for (const w of node.value.split(/\s+/).filter(Boolean)) {
          words.push({ text: w, ...style });
        }
        break;
      case "strong":
        words.push(...inlineToWords(node.children, { ...style, bold: true }));
        break;
      case "emphasis":
        words.push(...inlineToWords(node.children, { ...style, italic: true }));
        break;
      case "delete":
        words.push(...inlineToWords(node.children, { ...style, strike: true }));
        break;
      case "inlineCode":
        for (const w of node.value.split(/\s+/).filter(Boolean)) {
          words.push({ text: w, ...style, code: true });
        }
        break;
      case "link":
        words.push(...inlineToWords(node.children, { ...style, link: node.url }));
        break;
      case "break":
        words.push({ text: "\n", ...style, hardBreak: true });
        break;
      default:
        if (node.children) words.push(...inlineToWords(node.children, style));
    }
  }
  return words;
}

function setWordFont(doc, word, baseSize) {
  const isKannada = !word.code && containsKannada(word.text);
  let family = word.code || word.monospace ? "courier" : "helvetica";
  let variant = "normal";
  if (word.bold && word.italic) variant = "bolditalic";
  else if (word.bold) variant = "bold";
  else if (word.italic) variant = "italic";

  if (isKannada) {
    // The embedded Kannada font only has normal/bold weights (no
    // italic/bolditalic) -- fall back to bold-or-normal rather than
    // asking jsPDF for a variant that was never registered.
    family = KANNADA_FONT_FAMILY;
    variant = word.bold ? "bold" : "normal";
  }

  doc.setFont(family, variant);
  doc.setFontSize(word.code ? baseSize - 1 : baseSize);
  if (word.color) doc.setTextColor(...word.color);
  else if (word.link) doc.setTextColor(...COLOR.heading);
  else if (word.code) doc.setTextColor(...COLOR.code);
  else doc.setTextColor(...COLOR.body);
}

// Prints a run of styled words with greedy word-wrap inside
// [x, x + width]. Returns the cursor's y after the last line.
function printWords(cursor, words, x, width, baseSize, lineHeight) {
  const { doc } = cursor;
  let cursorX = x;
  ensureSpace(cursor, lineHeight);

  for (const word of words) {
    if (word.hardBreak) {
      cursor.y += lineHeight;
      ensureSpace(cursor, lineHeight);
      cursorX = x;
      continue;
    }
    setWordFont(doc, word, baseSize);
    const wWidth = doc.getTextWidth(word.text);
    const spW = doc.getTextWidth(" ");

    if (cursorX !== x && cursorX + wWidth > x + width) {
      cursor.y += lineHeight;
      ensureSpace(cursor, lineHeight);
      cursorX = x;
    }

    if (word.link) {
      doc.textWithLink(word.text, cursorX, cursor.y, { url: word.link });
      doc.setDrawColor(...COLOR.heading);
      doc.setLineWidth(0.15);
      doc.line(cursorX, cursor.y + 0.8, cursorX + wWidth, cursor.y + 0.8);
    } else {
      doc.text(word.text, cursorX, cursor.y);
      if (word.strike) {
        doc.setDrawColor(...COLOR.body);
        doc.setLineWidth(0.15);
        doc.line(cursorX, cursor.y - 1, cursorX + wWidth, cursor.y - 1);
      }
    }
    cursorX += wWidth + spW;
  }
  cursor.y += lineHeight;
  return cursor.y;
}

// --- Block-level mdast rendering -------------------------------------

const HEADING_SIZE = { 1: 13, 2: 12, 3: 11 };

function renderBlock(cursor, node, indent = 0) {
  const { doc } = cursor;
  const x = MARGIN_X + indent;
  const width = CONTENT_WIDTH - indent;

  switch (node.type) {
    case "heading": {
      cursor.y += 2;
      const size = HEADING_SIZE[node.depth] || 10;
      printWords(
        cursor,
        inlineToWords(node.children, { bold: true }),
        x,
        width,
        size,
        size * 0.45
      );
      cursor.y += 1;
      break;
    }

    case "paragraph": {
      printWords(cursor, inlineToWords(node.children), x, width, 10, 4.6);
      cursor.y += 1.5;
      break;
    }

    case "list": {
      node.children.forEach((item, i) => {
        renderListItem(cursor, item, indent, node.ordered ? i + 1 + (node.start || 1) - 1 : null);
      });
      cursor.y += 1;
      break;
    }

    case "blockquote": {
      const startY = cursor.y;
      cursor.y += 1;
      for (const child of node.children) {
        renderBlock(cursor, child, indent + 6);
      }
      verticalBar(doc, MARGIN_X + indent + 1, startY, cursor.y - 2, COLOR.heading);
      cursor.y += 1;
      break;
    }

    case "code": {
      renderCodeBlock(cursor, node.value || "", x, width);
      break;
    }

    case "table": {
      renderTable(cursor, node, x, width);
      break;
    }

    case "thematicBreak": {
      hr(cursor);
      break;
    }

    default: {
      // Fallback: flatten anything unhandled (e.g. html, image) to plain text.
      const text = mdastToString(node);
      if (text) {
        printWords(cursor, [{ text }].flatMap((w) => w.text.split(/\s+/).map((t) => ({ text: t }))), x, width, 10, 4.6);
      }
    }
  }
}

function renderListItem(cursor, item, indent, ordinal) {
  const bulletIndent = indent + 5;
  // "-" rather than a bullet glyph (e.g. U+2022) -- jsPDF's default core
  // fonts (Helvetica/Courier) only support WinAnsi encoding, and "•"
  // extracted as a mangled/replacement character in real PDF readers'
  // text layer (confirmed via pypdf text extraction), even though it
  // may look fine on screen in some renderers.
  const bullet = ordinal != null ? `${ordinal}.` : "-";
  const bulletX = MARGIN_X + indent;
  const textX = MARGIN_X + bulletIndent;
  const width = CONTENT_WIDTH - bulletIndent;

  ensureSpace(cursor, 4.6);
  const { doc } = cursor;
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.setTextColor(...COLOR.heading);
  doc.text(bullet, bulletX, cursor.y);

  for (const child of item.children) {
    if (child.type === "paragraph") {
      printWords(cursor, inlineToWords(child.children), textX, width, 10, 4.6);
    } else {
      renderBlock(cursor, child, bulletIndent);
    }
  }
}

function renderCodeBlock(cursor, code, x, width) {
  const { doc } = cursor;
  doc.setFont("courier", "normal");
  doc.setFontSize(8.5);
  const lines = code.split("\n").flatMap((line) => doc.splitTextToSize(line || " ", width - 6));
  const lineHeight = 4;
  const blockHeight = lines.length * lineHeight + 4;

  ensureSpace(cursor, Math.min(blockHeight, PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM));
  const top = cursor.y - 3;
  doc.setFillColor(...COLOR.codeBg);
  doc.rect(x, top, width, blockHeight, "F");

  cursor.y += 1;
  doc.setTextColor(...COLOR.code);
  for (const line of lines) {
    ensureSpace(cursor, lineHeight);
    doc.text(line, x + 3, cursor.y);
    cursor.y += lineHeight;
  }
  cursor.y += 3;
}

function renderTable(cursor, node, x, width) {
  const { doc } = cursor;
  const rows = node.children.map((row) =>
    row.children.map((cell) => mdastToString(cell))
  );
  if (rows.length === 0) return;

  const colCount = rows[0].length;
  const colWidth = width / colCount;
  const lineHeight = 5;

  rows.forEach((row, rowIndex) => {
    ensureSpace(cursor, lineHeight + 1);
    const isHeader = rowIndex === 0;
    if (isHeader) {
      doc.setFillColor(...COLOR.tableHeaderBg);
      doc.rect(x, cursor.y - 3.6, width, lineHeight, "F");
    }
    doc.setFontSize(9);
    doc.setTextColor(...COLOR.body);
    row.forEach((cellText, colIndex) => {
      // Font set per-cell, not once per row -- a cell can contain
      // Kannada text needing the embedded Unicode font while its
      // neighbors stay on helvetica.
      const variant = isHeader ? "bold" : "normal";
      doc.setFont(
        containsKannada(cellText) ? KANNADA_FONT_FAMILY : "helvetica",
        variant
      );
      const cellX = x + colIndex * colWidth + 1.5;
      const truncated = doc.splitTextToSize(cellText, colWidth - 3)[0] || "";
      doc.text(truncated, cellX, cursor.y);
    });
    doc.setDrawColor(...COLOR.tableBorder);
    doc.setLineWidth(0.1);
    doc.line(x, cursor.y + 1.4, x + width, cursor.y + 1.4);
    cursor.y += lineHeight;
  });
  cursor.y += 2;
}

// --- Message-level rendering ------------------------------------------

function renderMessageHeader(cursor, label, time, barColor) {
  const { doc } = cursor;
  ensureSpace(cursor, 6);
  doc.setFont("courier", "normal");
  doc.setFontSize(8);
  doc.setTextColor(...COLOR.muted);
  doc.text(time || "", MARGIN_X, cursor.y);

  doc.setFont("helvetica", "bold");
  doc.setFontSize(8.5);
  doc.setTextColor(...barColor);
  doc.text(label, MARGIN_X + 18, cursor.y);
  cursor.y += 5;
  return barColor;
}

function renderMessage(cursor, message) {
  const isQuery = message.role === "query";
  const barColor = isQuery ? COLOR.queryBar : message.error ? COLOR.errorBar : COLOR.resultBar;
  const startY = cursor.y - 3;

  renderMessageHeader(cursor, isQuery ? "QUERY" : message.error ? "ERROR" : "RESULT", message.time, barColor);

  const contentX = MARGIN_X + 6;
  const contentWidth = CONTENT_WIDTH - 6;

  if (isQuery || !message.text) {
    printWords(
      cursor,
      (message.text || "").split(/\s+/).filter(Boolean).map((t) => ({ text: t })),
      contentX,
      contentWidth,
      10,
      4.8
    );
  } else {
    const tree = markdownParser.parse(message.text);
    for (const child of tree.children) {
      renderBlock(cursor, child, 6);
    }
  }

  verticalBar(cursor.doc, MARGIN_X + 2, startY, cursor.y - 2, barColor);
  cursor.y += 3;
}

export async function exportConversationToPdf(messages, title) {
  if (!messages || messages.length === 0) return;

  await ensureLibsLoaded();

  const doc = new jsPDFCtor({ unit: "mm", format: "a4" });
  await registerKannadaFont(doc);
  const cursor = newCursor(doc);

  // Word-by-word (not doc.splitTextToSize on the whole string) so a
  // title that mixes English and Kannada -- e.g. auto-generated from a
  // Kannada first message -- gets each word measured/rendered in the
  // right font, the same way body text does. "monospace" keeps the
  // English portion in the terminal-style courier look; Kannada words
  // still switch to the embedded Unicode font regardless.
  const titleWords = (title || "Untitled Investigation")
    .toUpperCase()
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => ({ text: w, bold: true, monospace: true, color: COLOR.heading }));
  printWords(cursor, titleWords, MARGIN_X, CONTENT_WIDTH, 13, 6);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(8.5);
  doc.setTextColor(...COLOR.muted);
  doc.text(`Exported ${new Date().toLocaleString()}`, MARGIN_X, cursor.y);
  cursor.y += 4;
  hr(cursor);
  cursor.y += 3;

  for (const message of messages) {
    if (!message.text) continue;
    renderMessage(cursor, message);
  }

  doc.save(sanitizeFilename(title));
}
