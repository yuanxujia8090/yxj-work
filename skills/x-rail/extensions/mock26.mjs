import http from "node:http";

const script = JSON.parse(process.env.MOCK26_SCRIPT || "[]");
let index = 0;

const server = http.createServer((request, response) => {
  if (request.url === "/health") {
    response.writeHead(200, { "content-type": "text/plain" });
    response.end("ok");
    return;
  }
  const step = script[Math.min(index, Math.max(script.length - 1, 0))] || { status: 200, body: { ok: true } };
  index += 1;
  response.writeHead(step.status || 200, { "content-type": "application/json" });
  response.end(JSON.stringify(step.body ?? {}));
});

server.listen(0, "127.0.0.1", () => {
  const address = server.address();
  if (!address || typeof address === "string") {
    throw new Error("mock26 没有拿到端口");
  }
  process.stdout.write(`${JSON.stringify({ port: address.port })}\n`);
});
