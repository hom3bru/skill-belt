function parseDate(text) {
  const [datePart, timePart] = text.split(" ");
  return new Date(datePart + "T" + timePart + "Z").getDate();
}

module.exports = { parseDate };
