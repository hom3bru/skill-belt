export interface Row {
  id: string;
  name: string;
  amount: number;
}

export function parseCsv(text: string): Row[] {
  const [header, ...lines] = text.trim().split("\n");
  const columns = header.split(",");
  return lines.map((line) => {
    const cells = line.split(",");
    const record: Record<string, string> = {};
    columns.forEach((column, i) => {
      record[column] = cells[i];
    });
    return { id: record.id, name: record.name, amount: Number(record.amount) };
  });
}
