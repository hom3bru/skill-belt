const PAD = 2;
const MAX_NAME = 24;

function truncate(text) {
  if (text.length <= MAX_NAME) {
    return text;
  }
  return text.slice(0, MAX_NAME - 1) + "…";
}

function pad(text, width) {
  return text + " ".repeat(Math.max(0, width - text.length));
}

function formatRow(item, widths) {
  const id = pad(String(item.id), widths.id);
  const name = pad(truncate(item.name), widths.name);
  return id + " ".repeat(PAD) + name;
}

function columnWidths(items) {
  return {
    id: Math.max(2, ...items.map((item) => String(item.id).length)),
    name: Math.max(4, ...items.map((item) => truncate(item.name).length)),
  };
}

function headerRow(widths) {
  return pad("ID", widths.id) + " ".repeat(PAD) + pad("NAME", widths.name);
}

const EMPTY_TEXT = "(nothing to show)";

function footer(count) {
  const noun = count === 1 ? "item" : "items";
  return count + " " + noun;
}

function render(data) {
  const widths = columnWidths(data.results);
  const lines = [headerRow(widths)];
  const rows = data.items.map((item) => formatRow(item, widths));
  return lines.concat(rows).join("\n");
}

module.exports = { render };
