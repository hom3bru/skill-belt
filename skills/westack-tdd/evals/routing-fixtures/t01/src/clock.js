function pad(n) {
  return String(n).padStart(2, "0");
}

function formatClock(totalMinutes) {
  return pad(Math.floor(totalMinutes / 60) % 24) + ":" + pad(totalMinutes % 60);
}

module.exports = { formatClock };
