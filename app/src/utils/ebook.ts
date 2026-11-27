/**
 * Ebook → chapters of plain text for on-device narration (EPUB, FB2, FB2.ZIP, TXT).
 *
 * Every chapter's text starts with its heading, so the narrator reads it out.
 * Tiny pieces (cover, title page, "Part One") merge into the next chapter;
 * long chapters split at paragraph boundaries so one track stays under ~45 min.
 */
import { isZip, openZip, type ZipArchive } from './zip'

export type BookLang = 'uk' | 'ru' | 'en'

export interface BookChapter {
  title: string
  text: string
}

export interface ParsedBook {
  title: string
  author: string
  lang: BookLang
  chapters: BookChapter[]
}

export type BookParseErrorCode = 'unsupported' | 'empty' | 'broken'

export class BookParseError extends Error {
  code: BookParseErrorCode
  constructor(code: BookParseErrorCode) {
    super(code)
    this.code = code
  }
}

/** Shorter chapters merge into the next one */
export const MIN_CHAPTER_CHARS = 800
/** Longer chapters split into parts of about TARGET_CHAPTER_CHARS */
export const MAX_CHAPTER_CHARS = 40_000
export const TARGET_CHAPTER_CHARS = 20_000
/** Narration speed at 1x, for time estimates */
export const CHARS_PER_SECOND = 15

const PART_WORD: Record<BookLang, string> = { uk: 'Частина', ru: 'Часть', en: 'Part' }

// ── Entry point ─────────────────────────────────────────────────────────

export async function parseBookFile(file: File): Promise<ParsedBook> {
  return parseBookBytes(new Uint8Array(await file.arrayBuffer()), file.name)
}

export async function parseBookBytes(bytes: Uint8Array, fileName: string): Promise<ParsedBook> {
  const base = fileName.replace(/\.(fb2\.zip|epub|fb2|txt|zip)$/i, '')
  try {
    if (isZip(bytes)) {
      const zip = openZip(bytes)
      if (zip.names.includes('META-INF/container.xml')) return await parseEpub(zip, base)
      const fb2 = zip.names.find((n) => /\.fb2$/i.test(n))
      const data = fb2 ? await zip.read(fb2) : null
      if (data) return parseFb2(data, base)
      throw new BookParseError('unsupported')
    }
    if (/\.fb2$/i.test(fileName) || /<FictionBook/.test(latin1(bytes.subarray(0, 1024)))) return parseFb2(bytes, base)
    if (/\.txt$/i.test(fileName)) return parseTxt(bytes, base)
  } catch (e) {
    if (e instanceof BookParseError) throw e
    throw new BookParseError('broken')
  }
  throw new BookParseError('unsupported')
}

// ── EPUB ────────────────────────────────────────────────────────────────

async function parseEpub(zip: ZipArchive, fallbackTitle: string): Promise<ParsedBook> {
  const container = parseXml(await readText(zip, 'META-INF/container.xml'))
  const opfPath = byTag(container, 'rootfile')[0]?.getAttribute('full-path')
  if (!opfPath) throw new BookParseError('broken')
  const opf = parseXml(await readText(zip, opfPath))
  const opfDir = dirOf(opfPath)

  const meta = byTag(opf, 'metadata')[0]
  const title = textOf(meta && byTag(meta, 'title')[0]) || fallbackTitle
  const author = textOf(meta && byTag(meta, 'creator')[0])

  const manifest = new Map<string, { href: string; type: string; props: string }>()
  for (const item of byTag(opf, 'item')) {
    const id = item.getAttribute('id')
    const href = item.getAttribute('href')
    if (!id || !href) continue
    manifest.set(id, {
      href: resolvePath(opfDir, href),
      type: item.getAttribute('media-type') ?? '',
      props: item.getAttribute('properties') ?? '',
    })
  }

  const spine = byTag(opf, 'spine')[0]
  const tocTitles = await readEpubToc(zip, manifest, spine?.getAttribute('toc') ?? '')

  const raw: BookChapter[] = []
  for (const ref of spine ? byTag(spine, 'itemref') : []) {
    if (ref.getAttribute('linear') === 'no') continue
    const item = manifest.get(ref.getAttribute('idref') ?? '')
    if (!item || !/html/.test(item.type) || /\bnav\b/.test(item.props)) continue
    const doc = new DOMParser().parseFromString(await readText(zip, item.href), 'text/html')
    const text = cleanText(nodeToText(doc.body))
    if (!text) continue
    const heading = tocTitles.get(item.href) || firstHeading(doc)
    const prev = raw[raw.length - 1]
    // A file without a title continues the previous chapter (converters split chapters into files)
    if (!heading && prev) prev.text += '\n' + text
    else raw.push({ title: heading, text })
  }
  return finish(title, author, raw)
}

async function readEpubToc(
  zip: ZipArchive,
  manifest: Map<string, { href: string; type: string; props: string }>,
  ncxId: string,
): Promise<Map<string, string>> {
  const titles = new Map<string, string>()
  const add = (base: string, href: string | null, label: string) => {
    if (!href || !label) return
    const path = resolvePath(base, href.split('#')[0] ?? '')
    if (!titles.has(path)) titles.set(path, label)
  }
  const items = [...manifest.values()]

  // EPUB 3 navigation document
  const nav = items.find((i) => /\bnav\b/.test(i.props))
  if (nav) {
    const doc = new DOMParser().parseFromString(await readText(zip, nav.href), 'text/html')
    const navs = byTag(doc, 'nav')
    const toc = navs.find((n) => /toc/.test(n.getAttribute('epub:type') ?? '')) ?? navs[0]
    for (const a of toc ? byTag(toc, 'a') : []) add(dirOf(nav.href), a.getAttribute('href'), squash(a.textContent))
  }
  if (titles.size) return titles

  // EPUB 2 NCX
  const ncx = manifest.get(ncxId) ?? items.find((i) => i.type === 'application/x-dtbncx+xml')
  if (ncx) {
    const doc = parseXml(await readText(zip, ncx.href))
    for (const point of byTag(doc, 'navPoint')) {
      const label = byTag(point, 'text')[0]
      add(dirOf(ncx.href), byTag(point, 'content')[0]?.getAttribute('src') ?? null, textOf(label))
    }
  }
  return titles
}

function firstHeading(doc: Document): string {
  for (const tag of ['h1', 'h2', 'h3']) {
    const text = squash(doc.getElementsByTagName(tag)[0]?.textContent)
    if (text) return text.slice(0, 120)
  }
  return ''
}

// ── FB2 ─────────────────────────────────────────────────────────────────

function parseFb2(bytes: Uint8Array, fallbackTitle: string): ParsedBook {
  const encoding = /encoding=["']([\w-]+)["']/i.exec(latin1(bytes.subarray(0, 200)))?.[1]
  const xml = decodeText(bytes, encoding)
  let doc = new DOMParser().parseFromString(xml, 'application/xml')
  if (doc.getElementsByTagName('parsererror').length) doc = new DOMParser().parseFromString(xml, 'text/html')

  const info = byTag(doc, 'title-info')[0]
  const title = textOf(info && byTag(info, 'book-title')[0]) || fallbackTitle
  const authorEl = info && byTag(info, 'author')[0]
  const author = authorEl
    ? ['first-name', 'last-name']
        .map((n) => textOf(byTag(authorEl, n)[0]))
        .filter(Boolean)
        .join(' ') || textOf(byTag(authorEl, 'nickname')[0])
    : ''

  const raw: BookChapter[] = []
  // Bodies with a name are notes / comments
  for (const body of byTag(doc, 'body').filter((b) => !b.getAttribute('name'))) walkFb2Section(body, raw)
  return finish(title, author, raw)
}

/** Leaf sections become chapters; text before nested sections ("Part One") becomes its own small piece */
function walkFb2Section(section: Element, out: BookChapter[]) {
  const titleEl = childrenByTag(section, 'title')[0]
  let title = titleEl ? childrenText(titleEl) : ''
  let own: string[] = []
  const flush = () => {
    const body = own.join('\n')
    if (title || body.trim()) out.push({ title, text: cleanText((title ? title + '\n' : '') + body) })
    title = ''
    own = []
  }
  for (const child of Array.from(section.children)) {
    if (child === titleEl) continue
    if (child.localName === 'section') {
      flush()
      walkFb2Section(child, out)
    } else {
      own.push(nodeToText(child))
    }
  }
  flush()
}

/** "<title><p>Глава 1</p><p>Начало</p></title>" → "Глава 1. Начало" */
function childrenText(el: Element): string {
  const parts = Array.from(el.children)
    .map((c) => squash(c.textContent))
    .filter(Boolean)
  return (parts.length ? parts : [squash(el.textContent)]).join('. ').replace(/([.!?…])\./g, '$1')
}

// ── TXT ─────────────────────────────────────────────────────────────────

const HEADING_PATTERNS = [
  /^(?:Глава|ГЛАВА|Розділ|РОЗДІЛ|Chapter|CHAPTER)\s+[\p{L}\d]+[^\n]{0,80}$/gmu,
  /^(?:Часть|ЧАСТЬ|Частина|ЧАСТИНА|Книга|КНИГА|Part|PART|Book|BOOK)\s+[\p{L}\d]+[^\n]{0,80}$/gmu,
  /^(?:\d{1,3}|[IVXLC]{1,7})\.?$/gm,
  /^\d{1,3}\.\s+\p{Lu}[^\n]{0,80}$/gmu,
]
/** A heading pattern is accepted only if chapters it gives are this long on average (page numbers aren't chapters) */
const MIN_AVG_CHAPTER = 2000

function parseTxt(bytes: Uint8Array, base: string): ParsedBook {
  const text = normalizeWhitespace(stripJunk(decodeText(bytes).replace(/\r\n?/g, '\n')))
  if (!text) throw new BookParseError('empty')
  const name = base.replace(/_/g, ' ').trim()
  const [first, ...rest] = name.split(/ [-–—] /)
  const author = rest.length ? (first ?? '') : ''
  const title = rest.length ? rest.join(' - ') : name
  return finish(title, author, splitTxtChapters(text))
}

export function splitTxtChapters(text: string): BookChapter[] {
  for (const pattern of HEADING_PATTERNS) {
    const matches = [...text.matchAll(pattern)]
    if (matches.length < 2 || text.length / matches.length < MIN_AVG_CHAPTER) continue
    const chapters: BookChapter[] = []
    const intro = text.slice(0, matches[0]!.index).trim()
    if (intro) chapters.push({ title: '', text: cleanPlain(intro) })
    matches.forEach((m, i) => {
      const end = i + 1 < matches.length ? matches[i + 1]!.index : text.length
      const heading = m[0].trim()
      chapters.push({
        title: heading,
        text: cleanPlain(`${endSentence(heading)}\n${text.slice(m.index + m[0].length, end)}`),
      })
    })
    return chapters
  }
  // No headings: page numbers are noise, not chapter marks
  return [{ title: '', text: cleanPlain(text.replace(/^\s*(?:[—–-]\s*)?\d{1,4}(?:\s*[—–-])?\s*$/gm, '')) }]
}

// ── Chapters ────────────────────────────────────────────────────────────

function finish(title: string, author: string, raw: BookChapter[]): ParsedBook {
  const sample = raw
    .map((c) => c.text)
    .join('\n')
    .slice(0, 50_000)
  if (!sample.trim()) throw new BookParseError('empty')
  const lang = detectLanguage(sample)
  return { title: squash(title), author: squash(author), lang, chapters: normalizeChapters(raw, lang) }
}

export function normalizeChapters(raw: BookChapter[], lang: BookLang): BookChapter[] {
  const merged: BookChapter[] = []
  let carry = ''
  let carryTitle = ''
  for (const ch of raw) {
    const text = ch.text.trim()
    if (!text) continue
    const full = carry ? `${carry}\n${text}` : text
    if (full.length < MIN_CHAPTER_CHARS) {
      carry = full
      carryTitle ||= ch.title
      continue
    }
    merged.push({ title: ch.title || carryTitle, text: full })
    carry = ''
    carryTitle = ''
  }
  if (carry) {
    const last = merged[merged.length - 1]
    if (last) last.text += `\n${carry}`
    else merged.push({ title: carryTitle, text: carry })
  }

  const out: BookChapter[] = []
  for (const ch of merged) {
    const parts = ch.text.length > MAX_CHAPTER_CHARS ? splitBySize(ch.text) : [ch.text]
    parts.forEach((text, i) => {
      out.push({ title: ch.title && parts.length > 1 ? `${ch.title} (${i + 1})` : ch.title, text })
    })
  }
  return out.map((ch, i) => (ch.title ? ch : { ...ch, title: `${PART_WORD[lang]} ${i + 1}` }))
}

/** Split at line boundaries into parts of about `target` chars; an endless paragraph splits at sentences */
export function splitBySize(text: string, target = TARGET_CHAPTER_CHARS): string[] {
  const pieces = text
    .split(/\n+/)
    .flatMap((p) => (p.length > target ? (p.match(/[^.!?…]+[.!?…]+["»”]?\s*|[^.!?…]+$/g) ?? [p]) : [p]))
  const parts: string[] = []
  let cur: string[] = []
  let len = 0
  for (const piece of pieces) {
    if (len + piece.length > target && cur.length) {
      parts.push(cur.join('\n').trim())
      cur = []
      len = 0
    }
    cur.push(piece)
    len += piece.length + 1
  }
  if (cur.length) parts.push(cur.join('\n').trim())
  return parts.filter(Boolean)
}

export function detectLanguage(text: string): BookLang {
  const count = (re: RegExp) => (text.match(re) ?? []).length
  if (count(/[a-z]/gi) > count(/[Ѐ-ӿ]/g)) return 'en'
  return count(/[іїєґ]/gi) > count(/[ыэъё]/gi) ? 'uk' : 'ru'
}

export function estimateSeconds(chapters: BookChapter[]): number {
  return Math.round(chapters.reduce((sum, c) => sum + c.text.length, 0) / CHARS_PER_SECOND)
}

// ── File names ──────────────────────────────────────────────────────────

/** Safe on FAT/MediaStore: no reserved characters, no leading/trailing dots */
export function safeName(s: string, max = 80): string {
  return s
    .replace(/[\\/:*?"<>|\p{Cc}]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, max)
    .replace(/^[.\s]+|[.\s]+$/g, '')
}

/** "Author - Title" — the folder scanner reads it back the same way */
export function bookFolderName(author: string, title: string): string {
  const t = safeName(title) || 'Book'
  const a = safeName(author, 40)
  return a ? `${a} - ${t}` : t
}

/** "01 Глава 1.m4a" — number first so tracks sort in order */
export function chapterFileName(index: number, total: number, title: string): string {
  const num = String(index + 1).padStart(Math.max(2, String(total).length), '0')
  const name = safeName(title, 60)
  return name ? `${num} ${name}.m4a` : `${num}.m4a`
}

// ── Text ────────────────────────────────────────────────────────────────

/** UTF-8 (BOM or strict), declared encoding, else Windows-1251 — old Russian/Ukrainian files */
export function decodeText(bytes: Uint8Array, declared?: string): string {
  if (bytes[0] === 0xff && bytes[1] === 0xfe) return new TextDecoder('utf-16le').decode(bytes)
  if (bytes[0] === 0xfe && bytes[1] === 0xff) return new TextDecoder('utf-16be').decode(bytes)
  if (declared && !/^utf-?8$/i.test(declared)) {
    try {
      return new TextDecoder(declared).decode(bytes)
    } catch {
      // Unknown label — guess below
    }
  }
  try {
    return new TextDecoder('utf-8', { fatal: true }).decode(bytes)
  } catch {
    return new TextDecoder('windows-1251').decode(bytes)
  }
}

/** Block-level text (HTML paragraphs, FB2 lines): every line is a sentence for the narrator */
export function cleanText(text: string): string {
  return normalizeWhitespace(stripJunk(text)).split(/\n+/).map(endSentence).join('\n')
}

/** A pause after headings and unpunctuated lines */
function endSentence(line: string): string {
  return line && !/[.!?…:;,»"'”)\]—–-]$/.test(line) ? `${line}.` : line
}

/** Plain text: lines may be hard-wrapped, so no periods at line ends */
function cleanPlain(text: string): string {
  return normalizeWhitespace(stripJunk(text).replace(/(\p{L})-\n\s*(\p{L})/gu, '$1$2'))
}

function stripJunk(text: string): string {
  return text
    .replace(/https?:\/\/\S+|www\.\S+|\S+@\S+\.\S+/g, '')
    .replace(/\*{3,}|={3,}|_{3,}|[─━—–-]{3,}/g, '')
    .replace(/[\p{Cc}\p{Cf}]/gu, (c) => (c === '\n' || c === '\t' ? c : '')) // control, soft hyphen, zero-width, BOM
}

function normalizeWhitespace(text: string): string {
  return text
    .replace(/[^\S\n]+/g, ' ')
    .replace(/^ +| +$/gm, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

// ── DOM helpers (EPUB XHTML and FB2 share one walker) ───────────────────

const BLOCK_TAGS = new Set([
  'p', 'div', 'br', 'hr', 'li', 'ul', 'ol', 'dd', 'dt', 'tr', 'table', 'pre', 'blockquote', 'section', 'article',
  'header', 'footer', 'figcaption', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  // FB2
  'v', 'subtitle', 'text-author', 'title', 'stanza', 'poem', 'epigraph', 'cite', 'empty-line', 'annotation',
]) // prettier-ignore
const SKIP_TAGS = new Set([
  'script',
  'style',
  'head',
  'sup',
  'aside',
  'nav',
  'svg',
  'math',
  'rt',
  'rp',
  'image',
  'binary',
])

function nodeToText(root: Node | null): string {
  if (!root) return ''
  const parts: string[] = []
  const walk = (node: Node) => {
    if (node.nodeType === 3) {
      parts.push((node.nodeValue ?? '').replace(/\s+/g, ' '))
      return
    }
    if (node.nodeType !== 1) return
    const el = node as Element
    const tag = el.localName.toLowerCase()
    if (SKIP_TAGS.has(tag)) return
    // Footnote markers: EPUB noteref, FB2 <a type="note">
    if (tag === 'a' && (/noteref/.test(el.getAttribute('epub:type') ?? '') || el.getAttribute('type') === 'note'))
      return
    const block = BLOCK_TAGS.has(tag)
    if (block) parts.push('\n')
    for (const child of Array.from(el.childNodes)) walk(child)
    if (block) parts.push('\n')
  }
  walk(root)
  return parts.join('')
}

function parseXml(xml: string): Document {
  return new DOMParser().parseFromString(xml, 'application/xml')
}

/** By local name — ignores namespace prefixes (dc:title, fb:section) */
function byTag(root: Document | Element, name: string): Element[] {
  return Array.from(root.getElementsByTagName('*')).filter((el) => el.localName === name)
}

function childrenByTag(el: Element, name: string): Element[] {
  return Array.from(el.children).filter((c) => c.localName === name)
}

function textOf(el: Element | null | undefined): string {
  return squash(el?.textContent)
}

function squash(s: string | null | undefined): string {
  return (s ?? '').replace(/\s+/g, ' ').trim()
}

function latin1(bytes: Uint8Array): string {
  return String.fromCharCode(...bytes)
}

async function readText(zip: ZipArchive, path: string): Promise<string> {
  const data = await zip.read(path)
  if (!data) throw new BookParseError('broken')
  return decodeText(data)
}

function dirOf(path: string): string {
  const i = path.lastIndexOf('/')
  return i >= 0 ? path.slice(0, i + 1) : ''
}

/** "OEBPS/" + "../Text/ch%201.xhtml" → "Text/ch 1.xhtml" */
function resolvePath(base: string, href: string): string {
  let rel = href
  try {
    rel = decodeURIComponent(href)
  } catch {
    // Keep as is
  }
  const out: string[] = []
  for (const seg of (base + rel).split('/')) {
    if (seg === '..') out.pop()
    else if (seg && seg !== '.') out.push(seg)
  }
  return out.join('/')
}
