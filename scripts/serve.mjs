#!/usr/bin/env node
// Tiny static server for the GridSight repo. Serves files from the repo root so
// both /frontend/ and /contracts/sample/ resolve (mock mode + screenshots).
// Usage: node scripts/serve.mjs [port]   (default 8080)
import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const PORT = Number(process.argv[2] || 8080);
const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
  ".csv": "text/csv; charset=utf-8",
};

createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://${req.headers.host}`);
    let path = decodeURIComponent(url.pathname);
    if (path === "/") path = "/frontend/index.html";
    if (path.endsWith("/")) path += "index.html";
    const safe = normalize(path).replace(/^([/\\])+/, "");
    const file = join(ROOT, safe);
    if (!file.startsWith(ROOT)) {
      res.writeHead(403, { "Content-Type": "text/plain" });
      res.end("forbidden");
      return;
    }
    const info = await stat(file);
    if (info.isDirectory()) {
      res.writeHead(302, { Location: path + "/" });
      res.end();
      return;
    }
    const body = await readFile(file);
    res.writeHead(200, {
      "Content-Type": TYPES[extname(file).toLowerCase()] || "application/octet-stream",
      "Cache-Control": "no-store",
    });
    res.end(body);
  } catch {
    res.writeHead(404, { "Content-Type": "text/plain" });
    res.end("not found");
  }
}).listen(PORT, () => {
  console.log(`GridSight static server: http://localhost:${PORT}/frontend/`);
});