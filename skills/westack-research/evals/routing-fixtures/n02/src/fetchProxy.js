async function getJson(url) {
  const response = await fetch(url);
  return response.json();
}

module.exports = { getJson };
