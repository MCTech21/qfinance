#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

const projectRoot = path.resolve(__dirname, "..");
const buildDir = path.join(projectRoot, "build");
const forbiddenPattern = /expense-tracker|preview\.expense-tracker\.local/gi;

const backendUrl = (process.env.REACT_APP_BACKEND_URL || "").trim();
if (backendUrl && forbiddenPattern.test(backendUrl)) {
  console.error(`[ERROR] REACT_APP_BACKEND_URL contiene dominio prohibido: ${backendUrl}`);
  process.exit(1);
}

if (!fs.existsSync(buildDir)) {
  console.error("[ERROR] No existe frontend/build. Ejecuta el build antes de validar.");
  process.exit(1);
}

const filesToScan = [];
const enqueue = (target) => {
  const stat = fs.statSync(target);
  if (stat.isDirectory()) {
    for (const entry of fs.readdirSync(target)) {
      enqueue(path.join(target, entry));
    }
    return;
  }

  if (/\.(js|css|html|map|json|txt)$/i.test(target)) {
    filesToScan.push(target);
  }
};

enqueue(buildDir);

const findings = [];
for (const filePath of filesToScan) {
  const content = fs.readFileSync(filePath, "utf8");
  forbiddenPattern.lastIndex = 0;
  if (forbiddenPattern.test(content)) {
    findings.push(path.relative(projectRoot, filePath));
  }
}

if (findings.length > 0) {
  console.error("[ERROR] Se detectaron dominios prohibidos en el build:");
  findings.forEach((file) => console.error(` - ${file}`));
  process.exit(1);
}

console.log("[OK] Validación de build completada: sin patrones prohibidos.");
