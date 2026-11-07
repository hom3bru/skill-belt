import { Queue, Worker } from "bullmq";

const connection = { host: "localhost", port: 6379 };

export const emails = new Queue("emails", { connection });

export function startWorker(handler) {
  return new Worker("emails", handler, { connection, concurrency: 5 });
}
