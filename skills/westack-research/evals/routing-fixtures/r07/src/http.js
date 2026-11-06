export async function get(url) {
  const response = await fetch(url, { headers: { accept: "application/json" } });
  return response.json();
}
