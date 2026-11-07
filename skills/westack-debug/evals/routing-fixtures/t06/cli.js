const { fetchItems } = require("./api");
const { render } = require("./list");

async function main() {
  const data = await fetchItems();
  console.log(render(data));
}

main();
