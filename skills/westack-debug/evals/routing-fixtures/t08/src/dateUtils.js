function daysUntil(isoDate, now = new Date()) {
  const target = new Date(isoDate + "T00:00:00Z");
  const start = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  return Math.round((target.getTime() - start) / 86400000);
}

function isWeekend(isoDate) {
  const day = new Date(isoDate + "T00:00:00Z").getUTCDay();
  return day === 0 || day === 6;
}

module.exports = { daysUntil, isWeekend };
