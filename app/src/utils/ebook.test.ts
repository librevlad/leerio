import { describe, it, expect } from 'vitest'
import { isZip, openZip } from './zip'
import {
  BookParseError,
  MAX_CHAPTER_CHARS,
  MIN_CHAPTER_CHARS,
  bookFolderName,
  chapterFileName,
  decodeText,
  detectLanguage,
  estimateSeconds,
  normalizeChapters,
  parseBookBytes,
  safeName,
  splitBySize,
  splitTxtChapters,
} from './ebook'
import { cp1251, makeZip } from '../__tests__/ebookFixtures'

const enc = new TextEncoder()
const UK = 'Сонце сходило над рікою, і їжак біг через поле. Вона дивилася на нього й усміхалася. '
const RU = 'Солнце вставало над рекой, и ёжик бежал через поле. Она смотрела на него и улыбалась. '
const EN = 'The sun was rising over the river, and the hedgehog ran across the field. '
const long = (s: string, n = 1200) => s.repeat(Math.ceil(n / s.length))

// ── ZIP ─────────────────────────────────────────────────────────────────

describe('zip', () => {
  it('reads stored and deflated entries', async () => {
    for (const deflate of [false, true]) {
      const bytes = await makeZip({ 'a.txt': 'hello', 'dir/б.txt': 'привет' }, deflate)
      expect(isZip(bytes)).toBe(true)
      const zip = openZip(bytes)
      expect(zip.names).toEqual(['a.txt', 'dir/б.txt'])
      expect(new TextDecoder().decode((await zip.read('dir/б.txt'))!)).toBe('привет')
      expect(await zip.read('missing')).toBeNull()
    }
  })

  it('rejects non-zip data', () => {
    const bytes = enc.encode('just text')
    expect(isZip(bytes)).toBe(false)
    expect(() => openZip(bytes)).toThrow()
  })
})

// ── EPUB ────────────────────────────────────────────────────────────────

const CONTAINER = `<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>`

const xhtml = (body: string) =>
  `<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>x</title><style>p{}</style></head><body>${body}</body></html>`

describe('EPUB', () => {
  it('reads metadata, nav titles, merges cover and split files', async () => {
    const opf = `<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Тіні забутих предків</dc:title><dc:creator>Михайло Коцюбинський</dc:creator>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="cover" href="Text/cover.xhtml" media-type="application/xhtml+xml"/>
    <item id="c1" href="Text/ch1.xhtml" media-type="application/xhtml+xml"/>
    <item id="c2" href="Text/ch%202.xhtml" media-type="application/xhtml+xml"/>
    <item id="c2b" href="Text/ch2b.xhtml" media-type="application/xhtml+xml"/>
    <item id="notes" href="Text/notes.xhtml" media-type="application/xhtml+xml"/>
    <item id="img" href="Images/c.jpg" media-type="image/jpeg"/>
  </manifest>
  <spine><itemref idref="cover"/><itemref idref="c1"/><itemref idref="c2"/><itemref idref="c2b"/><itemref idref="notes" linear="no"/></spine>
</package>`
    const nav = xhtml(
      `<nav epub:type="toc"><ol><li><a href="Text/ch1.xhtml">Розділ перший</a></li><li><a href="Text/ch%202.xhtml#s">Розділ другий</a></li></ol></nav>`,
    )
    const bytes = await makeZip({
      mimetype: 'application/epub+zip',
      'META-INF/container.xml': CONTAINER,
      'OEBPS/content.opf': opf,
      'OEBPS/nav.xhtml': nav,
      'OEBPS/Text/cover.xhtml': xhtml('<p>Тіні забутих предків</p><img src="../Images/c.jpg"/>'),
      'OEBPS/Text/ch1.xhtml': xhtml(
        `<h2>Розділ перший</h2><p>${long(UK)}<sup><a epub:type="noteref" href="#n1">1</a></sup></p>`,
      ),
      'OEBPS/Text/ch 2.xhtml': xhtml(`<h2>Розділ другий</h2><p>${long(UK)}</p>`),
      'OEBPS/Text/ch2b.xhtml': xhtml('<p>Кінець другого розділу.</p>'),
      'OEBPS/Text/notes.xhtml': xhtml('<p>Примітка</p>'),
    })

    const book = await parseBookBytes(bytes, 'book.epub')
    expect(book.title).toBe('Тіні забутих предків')
    expect(book.author).toBe('Михайло Коцюбинський')
    expect(book.lang).toBe('uk')
    expect(book.chapters.map((c) => c.title)).toEqual(['Розділ перший', 'Розділ другий'])

    const [ch1, ch2] = book.chapters
    // Cover text is read before chapter 1, heading spoken, footnote marker skipped
    expect(ch1!.text.startsWith('Тіні забутих предків.\nРозділ перший.\n')).toBe(true)
    expect(ch1!.text).not.toMatch(/1$/)
    expect(ch1!.text).not.toContain('p{}')
    // Untitled continuation file joins its chapter; non-linear notes are skipped
    expect(ch2!.text.endsWith('Кінець другого розділу.')).toBe(true)
    expect(book.chapters.some((c) => c.text.includes('Примітка'))).toBe(false)
  })

  it('falls back to NCX titles and headings, resolves ../ paths', async () => {
    const opf = `<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Book</dc:title></metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="a" href="../Text/a.html" media-type="application/xhtml+xml"/>
    <item id="b" href="../Text/b.html" media-type="application/xhtml+xml"/>
  </manifest>
  <spine toc="ncx"><itemref idref="a"/><itemref idref="b"/></spine>
</package>`
    const ncx = `<?xml version="1.0"?><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/"><navMap>
  <navPoint id="p1"><navLabel><text>The Beginning</text></navLabel><content src="../Text/a.html"/></navPoint>
</navMap></ncx>`
    const bytes = await makeZip({
      'META-INF/container.xml': CONTAINER.replace('OEBPS/content.opf', 'OPS/book.opf'),
      'OPS/book.opf': opf,
      'OPS/toc.ncx': ncx,
      'Text/a.html': xhtml(`<p>${long(EN)}</p>`),
      'Text/b.html': xhtml(`<h1>Chapter Two</h1><div>${long(EN)}</div>`),
    })
    const book = await parseBookBytes(bytes, 'x.epub')
    expect(book.lang).toBe('en')
    expect(book.author).toBe('')
    expect(book.chapters.map((c) => c.title)).toEqual(['The Beginning', 'Chapter Two'])
  })
})

// ── FB2 ─────────────────────────────────────────────────────────────────

const fb2 = (encoding: string) => `<?xml version="1.0" encoding="${encoding}"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0" xmlns:l="http://www.w3.org/1999/xlink">
  <description><title-info>
    <author><first-name>Лев</first-name><middle-name>Николаевич</middle-name><last-name>Толстой</last-name></author>
    <book-title>Детство</book-title><lang>ru</lang>
  </title-info></description>
  <body>
    <title><p>Лев Толстой</p><p>Детство</p></title>
    <epigraph><p>Эпиграф к книге</p></epigraph>
    <section>
      <title><p>Часть первая</p></title>
      <section>
        <title><p>Глава I</p><p>Учитель</p></title>
        <p>${long(RU)}<a l:href="#n1" type="note">[1]</a></p>
      </section>
      <section>
        <title><p>Глава II</p></title>
        <p>${long(RU)}</p><empty-line/><p>Конец главы.</p>
      </section>
    </section>
  </body>
  <body name="notes"><section id="n1"><p>Сноска</p></section></body>
  <binary id="cover.jpg" content-type="image/jpeg">AAAA</binary>
</FictionBook>`

describe('FB2', () => {
  it('reads nested sections, skips notes, merges part title into its first chapter', async () => {
    const book = await parseBookBytes(enc.encode(fb2('utf-8')), 'detstvo.fb2')
    expect(book.title).toBe('Детство')
    expect(book.author).toBe('Лев Толстой')
    expect(book.lang).toBe('ru')
    expect(book.chapters.map((c) => c.title)).toEqual(['Глава I. Учитель', 'Глава II'])

    const [ch1, ch2] = book.chapters
    expect(ch1!.text.startsWith('Лев Толстой. Детство.\nЭпиграф к книге.\nЧасть первая.\nГлава I. Учитель.\n')).toBe(
      true,
    )
    expect(ch1!.text).not.toContain('[1]')
    expect(ch2!.text.endsWith('Конец главы.')).toBe(true)
    expect(book.chapters.some((c) => c.text.includes('Сноска'))).toBe(false)
  })

  it('decodes Windows-1251 and reads .fb2.zip', async () => {
    const bytes = cp1251(fb2('windows-1251'))
    const plain = await parseBookBytes(bytes, 'detstvo.fb2')
    expect(plain.author).toBe('Лев Толстой')
    expect(plain.chapters[0]!.title).toBe('Глава I. Учитель')

    const zipped = await parseBookBytes(await makeZip({ 'detstvo.fb2': bytes }), 'detstvo.fb2.zip')
    expect(zipped.chapters).toEqual(plain.chapters)
  })
})

// ── TXT ─────────────────────────────────────────────────────────────────

describe('TXT', () => {
  it('splits by chapter headings and takes author/title from the file name', async () => {
    const text = `Предисловие автора.\n\nГлава 1\n\n${long(RU, 2500)}\n\nГлава 2. Дорога\n${long(RU, 2500)}\n`
    const book = await parseBookBytes(enc.encode(text), 'Иван_Бунин_-_Тёмные аллеи.txt')
    expect(book.author).toBe('Иван Бунин')
    expect(book.title).toBe('Тёмные аллеи')
    expect(book.chapters.map((c) => c.title)).toEqual(['Глава 1', 'Глава 2. Дорога'])
    expect(book.chapters[0]!.text.startsWith('Предисловие автора.\nГлава 1.\n')).toBe(true)
    expect(book.chapters[1]!.text.startsWith('Глава 2. Дорога.\n')).toBe(true)
  })

  it('reads Ukrainian headings in Windows-1251', async () => {
    const text = `Розділ 1\r\n${long(UK, 2500)}\r\nРозділ 2\r\n${long(UK, 2500)}`
    const book = await parseBookBytes(cp1251(text), 'book.txt')
    expect(book.lang).toBe('uk')
    expect(book.chapters.map((c) => c.title)).toEqual(['Розділ 1', 'Розділ 2'])
  })

  it('does not take page numbers for chapters', () => {
    const page = long(RU, 600)
    const chapters = splitTxtChapters(`${page}\n12\n${page}\n13\n${page}`)
    expect(chapters).toHaveLength(1)
    expect(chapters[0]!.text).not.toMatch(/^1[23]$/m)
  })

  it('joins words hyphenated across lines', () => {
    expect(splitTxtChapters('Это было про-\nдолжение')[0]!.text).toBe('Это было продолжение')
  })

  it('rejects empty and unknown files', async () => {
    await expect(parseBookBytes(enc.encode('  \n '), 'a.txt')).rejects.toMatchObject({ code: 'empty' })
    await expect(parseBookBytes(enc.encode('%PDF-1.4'), 'a.pdf')).rejects.toBeInstanceOf(BookParseError)
    await expect(parseBookBytes(await makeZip({ 'a.mp3': 'x' }), 'a.zip')).rejects.toMatchObject({
      code: 'unsupported',
    })
  })
})

// ── Chapters ────────────────────────────────────────────────────────────

describe('normalizeChapters', () => {
  it('merges small pieces into the next chapter, a small tail into the last one', () => {
    const out = normalizeChapters(
      [
        { title: '', text: 'Title page' },
        { title: 'Part One', text: 'Part One.' },
        { title: 'Chapter 1', text: long(EN) },
        { title: 'Chapter 2', text: long(EN) },
        { title: 'Afterword', text: 'Thanks.' },
      ],
      'en',
    )
    expect(out.map((c) => c.title)).toEqual(['Chapter 1', 'Chapter 2'])
    expect(out[0]!.text.startsWith('Title page\nPart One.\n')).toBe(true)
    expect(out[1]!.text.endsWith('\nThanks.')).toBe(true)
  })

  it('splits long chapters and names untitled ones', () => {
    const out = normalizeChapters(
      [
        { title: '', text: long(UK, MIN_CHAPTER_CHARS) },
        { title: 'Довгий', text: long(UK, MAX_CHAPTER_CHARS + 5000).replace(/\. /g, '.\n') },
      ],
      'uk',
    )
    expect(out[0]!.title).toBe('Частина 1')
    expect(out.slice(1).map((c) => c.title)).toEqual(['Довгий (1)', 'Довгий (2)', 'Довгий (3)'])
    for (const c of out) expect(c.text.length).toBeLessThanOrEqual(MAX_CHAPTER_CHARS)
  })

  it('keeps a single short book as one chapter', () => {
    expect(normalizeChapters([{ title: '', text: 'Коротко.' }], 'ru')).toEqual([{ title: 'Часть 1', text: 'Коротко.' }])
  })
})

describe('splitBySize', () => {
  it('cuts at line boundaries near the target', () => {
    const parts = splitBySize(Array(10).fill('x'.repeat(99)).join('\n'), 300)
    expect(parts).toHaveLength(4)
    expect(parts[0]!.split('\n')).toHaveLength(3)
  })

  it('cuts an endless paragraph at sentences', () => {
    const parts = splitBySize('Раз два три. '.repeat(100), 200)
    expect(parts.length).toBeGreaterThan(5)
    for (const p of parts) expect(p.endsWith('.')).toBe(true)
  })
})

describe('helpers', () => {
  it('detects language', () => {
    expect(detectLanguage(UK)).toBe('uk')
    expect(detectLanguage(RU)).toBe('ru')
    expect(detectLanguage(EN)).toBe('en')
  })

  it('decodes UTF-8, BOM and Windows-1251', () => {
    expect(decodeText(new Uint8Array([0xef, 0xbb, 0xbf, ...enc.encode('Привіт')]))).toBe('Привіт')
    expect(decodeText(cp1251('Привіт, їжак'))).toBe('Привіт, їжак')
  })

  it('builds safe folder and track names', () => {
    expect(safeName('  a/b:c?  ')).toBe('a b c')
    expect(safeName('...Title...')).toBe('Title')
    expect(bookFolderName('Тарас Шевченко', 'Кобзар: вибране')).toBe('Тарас Шевченко - Кобзар вибране')
    expect(bookFolderName('', '')).toBe('Book')
    expect(chapterFileName(0, 12, 'Глава 1. Начало')).toBe('01 Глава 1. Начало.m4a')
    expect(chapterFileName(4, 120, '')).toBe('005.m4a')
  })

  it('estimates narration time', () => {
    expect(estimateSeconds([{ title: '', text: 'x'.repeat(1500) }])).toBe(100)
  })
})
