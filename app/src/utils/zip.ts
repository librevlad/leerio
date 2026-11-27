/**
 * Minimal ZIP reader for EPUB and .fb2.zip: central directory + stored/deflate entries.
 * Inflate goes through the platform's DecompressionStream — no library.
 */

export interface ZipArchive {
  names: string[]
  read(name: string): Promise<Uint8Array | null>
}

const EOCD_SIG = 0x06054b50
const CENTRAL_SIG = 0x02014b50
const LOCAL_SIG = 0x04034b50

interface Entry {
  method: number
  compressedSize: number
  localOffset: number
}

export function isZip(bytes: Uint8Array): boolean {
  return bytes.length > 4 && bytes[0] === 0x50 && bytes[1] === 0x4b && bytes[2] === 0x03 && bytes[3] === 0x04
}

export function openZip(bytes: Uint8Array): ZipArchive {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)

  // End of central directory: last 22 bytes + up to 64 KB comment
  let eocd = -1
  for (let i = bytes.length - 22; i >= Math.max(0, bytes.length - 22 - 0xffff); i--) {
    if (view.getUint32(i, true) === EOCD_SIG) {
      eocd = i
      break
    }
  }
  if (eocd < 0) throw new Error('Not a ZIP file')

  const count = view.getUint16(eocd + 10, true)
  let pos = view.getUint32(eocd + 16, true)
  const entries = new Map<string, Entry>()
  const utf8 = new TextDecoder()

  for (let i = 0; i < count; i++) {
    if (pos + 46 > bytes.length || view.getUint32(pos, true) !== CENTRAL_SIG) break
    const method = view.getUint16(pos + 10, true)
    const compressedSize = view.getUint32(pos + 20, true)
    const nameLen = view.getUint16(pos + 28, true)
    const extraLen = view.getUint16(pos + 30, true)
    const commentLen = view.getUint16(pos + 32, true)
    const localOffset = view.getUint32(pos + 42, true)
    const name = utf8.decode(bytes.subarray(pos + 46, pos + 46 + nameLen))
    entries.set(name, { method, compressedSize, localOffset })
    pos += 46 + nameLen + extraLen + commentLen
  }

  async function read(name: string): Promise<Uint8Array | null> {
    const entry = entries.get(name)
    if (!entry) return null
    const p = entry.localOffset
    if (view.getUint32(p, true) !== LOCAL_SIG) return null
    const start = p + 30 + view.getUint16(p + 26, true) + view.getUint16(p + 28, true)
    const data = bytes.subarray(start, start + entry.compressedSize)
    if (entry.method === 0) return data
    if (entry.method !== 8) throw new Error(`Unsupported ZIP method ${entry.method}`)
    return inflateRaw(data)
  }

  return { names: [...entries.keys()], read }
}

async function inflateRaw(data: Uint8Array): Promise<Uint8Array> {
  const stream = new Blob([data as BlobPart]).stream().pipeThrough(new DecompressionStream('deflate-raw'))
  return new Uint8Array(await new Response(stream).arrayBuffer())
}
