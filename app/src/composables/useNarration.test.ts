import { describe, it, expect } from 'vitest'
import { narrationToFsBook, sortVoices, voiceLabel, voiceLanguages, type TtsVoice } from './useNarration'

const voice = (over: Partial<TtsVoice>): TtsVoice => ({
  id: `${over.engine ?? 'g'}/${over.name ?? 'v'}`,
  engine: 'com.google.android.tts',
  engineLabel: 'Google',
  name: 'v',
  lang: 'uk-UA',
  quality: 300,
  isDefault: false,
  ...over,
})

describe('narrationToFsBook', () => {
  it('turns a finished job into an fs: library book', () => {
    const book = narrationToFsBook(
      {
        state: 'done',
        dir: 'Audiobooks/Леся Українка - Лісова пісня',
        title: 'Лісова пісня',
        author: 'Леся Українка',
        files: [
          {
            index: 0,
            title: 'Пролог',
            path: 'Audiobooks/Леся Українка - Лісова пісня/01 Пролог.m4a',
            durationMs: 61_400,
            size: 1000,
          },
          {
            index: 1,
            title: 'Дія I',
            path: 'Audiobooks/Леся Українка - Лісова пісня/02 Дія I.m4a',
            durationMs: 1_200_000,
            size: 2000,
          },
        ],
      },
      new Date('2026-11-27T10:00:00Z'),
    )
    expect(book).toEqual({
      id: 'fs:Леся Українка - Лісова пісня',
      title: 'Лісова пісня',
      author: 'Леся Українка',
      folderPath: 'Audiobooks/Леся Українка - Лісова пісня',
      tracks: [
        {
          index: 0,
          filename: '01 Пролог.m4a',
          path: 'Audiobooks/Леся Українка - Лісова пісня/01 Пролог.m4a',
          duration: 61,
        },
        {
          index: 1,
          filename: '02 Дія I.m4a',
          path: 'Audiobooks/Леся Українка - Лісова пісня/02 Дія I.m4a',
          duration: 1200,
        },
      ],
      sizeBytes: 3000,
      synced: false,
      addedAt: '2026-11-27T10:00:00.000Z',
    })
  })

  it('makes nothing from a job without files', () => {
    expect(narrationToFsBook({ state: 'cancelled', dir: 'Audiobooks/X', files: [] })).toBeNull()
    expect(narrationToFsBook({ state: 'error' })).toBeNull()
  })
})

describe('voices', () => {
  const samsung = voice({
    engine: 'com.samsung.SMT',
    engineLabel: 'Samsung',
    name: 's1',
    lang: 'ru-RU',
    isDefault: true,
  })
  const g1 = voice({ name: 'g1', lang: 'ru-RU', quality: 400 })
  const g2 = voice({ name: 'g2', lang: 'ru-RU', isDefault: true })
  const gUk = voice({ name: 'u1', lang: 'uk-UA' })

  it('puts the default engine and its default voice first', () => {
    const sorted = sortVoices([g1, samsung, g2], 'com.google.android.tts')
    expect(sorted.map((v) => v.name)).toEqual(['g2', 'g1', 's1'])
  })

  it('lists the book language first, then uk/ru/en', () => {
    const de = voice({ name: 'd', lang: 'de-DE' })
    expect(voiceLanguages([de, g1, gUk], 'en')).toEqual(['en', 'uk', 'ru', 'de'])
  })

  it('labels voices by engine, locale and number', () => {
    const ru = [g1, g2, samsung]
    expect(voiceLabel(g2, ru)).toBe('Google · ru-RU · 2')
    expect(voiceLabel(samsung, ru)).toBe('Samsung · ru-RU')
  })
})
