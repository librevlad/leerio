import { describe, it, expect } from 'vitest'
import { presignGet } from './s3'

// Expected links: boto3 generate_presigned_url (path style, region auto) at the same fixed time, fake keys
const cfg = {
  endpoint: 'https://0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com',
  bucket: 'leerio-books',
  accessKey: 'TESTACCESSKEY0123456789',
  secretKey: 'testsecretkey/with+chars0123456789abcdef',
}
const now = new Date('2026-11-27T12:00:00Z')
const base = 'https://0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com/leerio-books/'
const query =
  'X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=TESTACCESSKEY0123456789%2F20261127%2Fauto%2Fs3%2Faws4_request' +
  '&X-Amz-Date=20261127T120000Z&X-Amz-Expires=3600&X-Amz-SignedHeaders=host&X-Amz-Signature='

describe('presignGet', () => {
  it('signs a plain key exactly like boto3', async () => {
    expect(await presignGet(cfg, 'library.json', 3600, now)).toBe(
      `${base}library.json?${query}96d7e2abf594b9853a80358266542e27feb2417b2f233159a22e414627ad22ad`,
    )
  })

  it('a Cyrillic folder with «», [] and ! is encoded and signed like boto3', async () => {
    const key = 'books/Брайан Трейси «Нет оправданий!» [чит. Станислав Иванов]/01__Brajan_Trejsi___Net_opravdan.mp3'
    expect(await presignGet(cfg, key, 3600, now)).toBe(
      `${base}books/%D0%91%D1%80%D0%B0%D0%B9%D0%B0%D0%BD%20%D0%A2%D1%80%D0%B5%D0%B9%D1%81%D0%B8%20%C2%AB%D0%9D%D0%B5%D1%82%20%D0%BE%D0%BF%D1%80%D0%B0%D0%B2%D0%B4%D0%B0%D0%BD%D0%B8%D0%B9%21%C2%BB%20%5B%D1%87%D0%B8%D1%82.%20%D0%A1%D1%82%D0%B0%D0%BD%D0%B8%D1%81%D0%BB%D0%B0%D0%B2%20%D0%98%D0%B2%D0%B0%D0%BD%D0%BE%D0%B2%5D/01__Brajan_Trejsi___Net_opravdan.mp3?${query}ba63a825e2ef5269fea19777a629048d972abe5e0c140f0d0c10e66e65ff0ac8`,
    )
  })

  it('nested folders keep their slashes; ( ) & + are encoded', async () => {
    expect(await presignGet(cfg, 'books/A (2)/CD 1/01 x&y+z.mp3', 3600, now)).toBe(
      `${base}books/A%20%282%29/CD%201/01%20x%26y%2Bz.mp3?${query}f39410c090c04078e5e689917f393e621707ac215e65e7ced12bd45a6be3ea8c`,
    )
  })
})
