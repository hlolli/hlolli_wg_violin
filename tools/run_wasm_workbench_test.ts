#!/usr/bin/env bun
/** Compile and play the prepared violin source with the browser workbench. */

import { pathToFileURL } from "node:url"
import { resolve } from "node:path"

interface Options {
  compilerRoot: string
  source: string
  csd: string
  output?: string
}

function parseOptions(): Options {
  const values = process.argv.slice(2)
  const result: Partial<Options> = {}
  for (let index = 0; index < values.length; index += 2) {
    const name = values[index]
    const value = values[index + 1]
    if (!name?.startsWith("--") || value === undefined) {
      throw new Error("expected --name value arguments")
    }
    if (name === "--compiler-root") result.compilerRoot = value
    else if (name === "--source") result.source = value
    else if (name === "--csd") result.csd = value
    else if (name === "--output") result.output = value
    else throw new Error(`unknown argument: ${name}`)
  }
  if (!result.compilerRoot || !result.source || !result.csd) {
    throw new Error("--compiler-root, --source, and --csd are required")
  }
  return result as Options
}

async function importFrom(path: string): Promise<any> {
  return import(pathToFileURL(path).href)
}

async function browserFactory(compilerRoot: string): Promise<any> {
  const entry = resolve(
    compilerRoot,
    "node_modules/@csound/browser/dist/csound.js"
  )
  const source = await Bun.file(entry).text()
  const expected =
    "const Csound = kd; const libcsound = __lcs__; export { Csound, libcsound }; export default Csound;"
  if (!source.includes(expected)) {
    throw new Error("the pinned Csound browser entry changed")
  }
  return new Function(source.replace(expected, "return __lcs__;"))()
}

async function main(): Promise<void> {
  const options = parseOptions()
  const compilerRoot = resolve(options.compilerRoot)
  const source = await Bun.file(options.source).text()
  const csd = await Bun.file(options.csd).text()
  const compileModule = await importFrom(
    resolve(compilerRoot, "src/compiler/compile.ts")
  )
  const archiveModule = await importFrom(
    resolve(compilerRoot, "src/compiler/sdk-archive.ts")
  )
  const archive = new Uint8Array(
    await Bun.file(
      resolve(
        compilerRoot,
        "node_modules/@csound/wasm-bin/lib/csound-plugin-sdk.tar.gz"
      )
    ).arrayBuffer()
  )
  const headers = archiveModule.extractCsoundHeaders(Bun.gunzipSync(archive))
  await compileModule.initializeCompiler(() => {})
  const result = await compileModule.compilePlugin(source, "c", headers)
  if (!result.ok || !(result.wasm instanceof ArrayBuffer)) {
    const details = result.diagnostics
      ?.map((row: { line: number; message: string }) =>
        `${row.line}: ${row.message}`
      )
      .join("\n")
    throw new Error(details || result.message || "browser compile failed")
  }
  const wasm = result.wasm
  const module = await WebAssembly.compile(wasm)
  const exports = new Set(
    WebAssembly.Module.exports(module).map((entry) => entry.name)
  )
  if (!exports.has("__wasm_call_ctors") || !exports.has("csound_opcode_init")) {
    throw new Error("browser plugin lacks required exports")
  }

  Object.defineProperty(globalThis, "window", {
    value: {
      atob: globalThis.atob.bind(globalThis),
      btoa: globalThis.btoa.bind(globalThis),
      webkitAudioContext: undefined
    },
    configurable: true
  })
  let blocks = 0
  try {
    const factory = await browserFactory(compilerRoot)
    const api = await factory({ withPlugins: [wasm] })
    const csound = api.csoundCreate()
    try {
      if (api.csoundCompileCSD(csound, csd) !== 0) {
        throw new Error("browser Csound rejected the smoke CSD")
      }
      if (api.csoundStart(csound) !== 0) {
        throw new Error("browser Csound did not start")
      }
      let status = 0
      while (status === 0 && blocks < 10_000) {
        status = api.csoundPerformKsmps(csound)
        blocks += 1
      }
      if (status === 0) throw new Error("browser score did not end")
    } finally {
      api.csoundDestroy(csound)
    }
  } finally {
    Reflect.deleteProperty(globalThis, "window")
  }

  const facts = {
    schema_version: 1,
    source_bytes: new TextEncoder().encode(source).byteLength,
    wasm_bytes: wasm.byteLength,
    performed_blocks: blocks
  }
  if (options.output) {
    await Bun.write(options.output, `${JSON.stringify(facts, null, 2)}\n`)
  }
  console.log(
    `PASS WASM: source=${facts.source_bytes} wasm=${facts.wasm_bytes} ` +
      `blocks=${facts.performed_blocks}`
  )
}

await main().catch((error) => {
  console.error(`WASM workbench test failed: ${error}`)
  process.exit(1)
})
