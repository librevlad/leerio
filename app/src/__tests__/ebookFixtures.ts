/** Test helper: builds a ZIP (stored or deflated entries, CRC left at 0 — the reader ignores it) */
export async function makeZip(files: Record<string, string | Uint8Array>, deflate = true): Promise<Uint8Array> {
  const enc = new TextEncoder()
  const locals: Uint8Array[] = []
  const centrals: Uint8Array[] = []
  let offset = 0

  for (const [name, content] of Object.entries(files)) {
    const raw = typeof content === 'string' ? enc.encode(content) : content
    const data = deflate ? await deflateRaw(raw) : raw
    const nameBytes = enc.encode(name)

    const local = new Uint8Array(30 + nameBytes.length + data.length)
    const lv = new DataView(local.buffer)
    lv.setUint32(0, 0x04034b50, true)
    lv.setUint16(8, deflate ? 8 : 0, true)
    lv.setUint32(18, data.length, true)
    lv.setUint32(22, raw.length, true)
    lv.setUint16(26, nameBytes.length, true)
    local.set(nameBytes, 30)
    local.set(data, 30 + nameBytes.length)

    const central = new Uint8Array(46 + nameBytes.length)
    const cv = new DataView(central.buffer)
    cv.setUint32(0, 0x02014b50, true)
    cv.setUint16(10, deflate ? 8 : 0, true)
    cv.setUint32(20, data.length, true)
    cv.setUint32(24, raw.length, true)
    cv.setUint16(28, nameBytes.length, true)
    cv.setUint32(42, offset, true)
    central.set(nameBytes, 46)

    locals.push(local)
    centrals.push(central)
    offset += local.length
  }

  const centralSize = centrals.reduce((s, c) => s + c.length, 0)
  const eocd = new Uint8Array(22)
  const ev = new DataView(eocd.buffer)
  ev.setUint32(0, 0x06054b50, true)
  ev.setUint16(8, centrals.length, true)
  ev.setUint16(10, centrals.length, true)
  ev.setUint32(12, centralSize, true)
  ev.setUint32(16, offset, true)

  const out = new Uint8Array(offset + centralSize + 22)
  let p = 0
  for (const part of [...locals, ...centrals, eocd]) {
    out.set(part, p)
    p += part.length
  }
  return out
}

async function deflateRaw(data: Uint8Array): Promise<Uint8Array> {
  const stream = new Blob([data as BlobPart]).stream().pipeThrough(new CompressionStream('deflate-raw'))
  return new Uint8Array(await new Response(stream).arrayBuffer())
}

const CP1251_EXTRA: Record<string, number> = { Ё: 0xa8, ё: 0xb8, І: 0xb2, і: 0xb3, Ї: 0xaf, ї: 0xbf, Є: 0xaa, є: 0xba, Ґ: 0xa5, ґ: 0xb4, '—': 0x97, '«': 0xab, '»': 0xbb } // prettier-ignore

/** Windows-1251 bytes for Cyrillic test text */
export function cp1251(text: string): Uint8Array {
  return Uint8Array.from([...text], (ch) => {
    const code = ch.charCodeAt(0)
    if (code < 0x80) return code
    if (code >= 0x410 && code <= 0x44f) return code - 0x410 + 0xc0
    const extra = CP1251_EXTRA[ch]
    if (extra === undefined) throw new Error(`No cp1251 byte for ${ch}`)
    return extra
  })
}
