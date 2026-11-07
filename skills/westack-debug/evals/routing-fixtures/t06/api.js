async function fetchItems() {
  return { results: [{ id: 1, name: "alpha" }, { id: 2, name: "beta" }], total: 2 };
}

module.exports = { fetchItems };
