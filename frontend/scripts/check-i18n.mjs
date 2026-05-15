#!/usr/bin/env node
// Verifica que los 6 locales tengan exactamente el mismo set de leaf keys que es
// (source of truth). Falla con exit 1 si hay drift; pensado para CI / pre-commit.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const localesDir = path.resolve(here, "..", "src", "locales");
const SOURCE = "es";
const LOCALES = ["es", "en", "de", "fr", "ja", "pt"];

function leafPaths(obj, prefix = "") {
  if (typeof obj !== "object" || obj === null) return [prefix];
  return Object.keys(obj).flatMap((k) =>
    leafPaths(obj[k], prefix ? `${prefix}.${k}` : k),
  );
}

function load(code) {
  const file = path.join(localesDir, code, "common.json");
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

const sourceKeys = new Set(leafPaths(load(SOURCE)));
let ok = true;

for (const code of LOCALES) {
  if (code === SOURCE) {
    console.log(`· ${code} (source, ${sourceKeys.size} keys)`);
    continue;
  }
  const otherKeys = new Set(leafPaths(load(code)));
  const missing = [...sourceKeys].filter((k) => !otherKeys.has(k));
  const extra = [...otherKeys].filter((k) => !sourceKeys.has(k));
  if (missing.length === 0 && extra.length === 0) {
    console.log(`✓ ${code} (${otherKeys.size} keys)`);
  } else {
    ok = false;
    console.error(`✗ ${code}:`);
    for (const k of missing) console.error(`    missing: ${k}`);
    for (const k of extra) console.error(`    extra:   ${k}`);
  }
}

if (!ok) {
  console.error(`\ni18n parity check failed. ${SOURCE} is the source of truth.`);
  process.exit(1);
}
console.log(`\nAll ${LOCALES.length} locales aligned.`);
