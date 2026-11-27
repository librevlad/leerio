/**
 * Presigned GET links for a private S3 bucket (Cloudflare R2 speaks S3): AWS Signature V4, query auth,
 * path-style URLs. WebCrypto only — no SDK in the bundle.
 */

export interface S3Config {
  /** https://<account>.r2.cloudflarestorage.com */
  endpoint: string
  bucket: string
  accessKey: string
  secretKey: string
  /** R2: "auto" */
  region?: string
}

const enc = new TextEncoder()

/** RFC 3986: everything except A–Z a–z 0–9 - . _ ~ is percent-encoded (UTF-8); keys keep their "/" */
function uriEncode(s: string, keepSlash = false): string {
  let out = ''
  for (const b of enc.encode(s)) {
    const c = String.fromCharCode(b)
    out +=
      /[A-Za-z0-9\-._~]/.test(c) || (keepSlash && c === '/') ? c : '%' + b.toString(16).toUpperCase().padStart(2, '0')
  }
  return out
}

function hex(buf: ArrayBuffer): string {
  return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, '0')).join('')
}

async function hmac(key: BufferSource, data: string): Promise<ArrayBuffer> {
  const k = await crypto.subtle.importKey('raw', key, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'])
  return crypto.subtle.sign('HMAC', k, enc.encode(data))
}

/** A GET link to one object, valid for `expiresSec` from `now` */
export async function presignGet(cfg: S3Config, key: string, expiresSec = 3600, now = new Date()): Promise<string> {
  const { origin, host } = new URL(cfg.endpoint)
  const region = cfg.region || 'auto'
  const amzDate = now
    .toISOString()
    .replace(/\.\d{3}/, '')
    .replace(/[-:]/g, '') // 20261127T120000Z
  const day = amzDate.slice(0, 8)
  const scope = `${day}/${region}/s3/aws4_request`
  const path = `/${uriEncode(cfg.bucket)}/${uriEncode(key, true)}`
  // Already in the sorted order the signature needs
  const query = [
    ['X-Amz-Algorithm', 'AWS4-HMAC-SHA256'],
    ['X-Amz-Credential', `${cfg.accessKey}/${scope}`],
    ['X-Amz-Date', amzDate],
    ['X-Amz-Expires', String(expiresSec)],
    ['X-Amz-SignedHeaders', 'host'],
  ]
    .map(([k, v]) => `${k}=${uriEncode(v!)}`)
    .join('&')
  const canonical = ['GET', path, query, `host:${host}`, '', 'host', 'UNSIGNED-PAYLOAD'].join('\n')
  const digest = hex(await crypto.subtle.digest('SHA-256', enc.encode(canonical)))
  const toSign = ['AWS4-HMAC-SHA256', amzDate, scope, digest].join('\n')

  let k = await hmac(enc.encode('AWS4' + cfg.secretKey), day)
  for (const part of [region, 's3', 'aws4_request']) k = await hmac(k, part)
  const signature = hex(await hmac(k, toSign))
  return `${origin}${path}?${query}&X-Amz-Signature=${signature}`
}
