# Multi-Source Architecture Spec

## Sources

```ts
type Source = 'catalog' | 'upload' | 'youtube' | 'torrent'
```

## YouTube Integration

- YouTube iframe API (no youtube-dl, no server download)
- Paste URL → fetch metadata (title, thumbnail, duration) via oEmbed
- Play via iframe embed or stream URL
- Book.source = 'youtube', Track.source_type = 'stream'
- NOT stored on server — client-side only
- Edge cases: invalid URL, private video, region block

## Torrent Integration

- WebTorrent (browser-only, no server involvement)
- Paste magnet link or drop .torrent file
- Parse files, filter audio (.mp3, .m4a, .aac)
- folder → Book, files → Tracks
- Playback before full download (streaming)
- Storage: IndexedDB cache
- NOT synced to server

## Unified Player Engine

```ts
interface AudioAdapter {
  play(track: Track): Promise<void>
  pause(): void
  seek(time: number): void
  setSpeed(rate: number): void
  getCurrentTime(): number
  getDuration(): number
  onEnded(cb: () => void): void
}
```

Adapters:
- FileAdapter (catalog/upload — current HTMLAudioElement)
- YouTubeAdapter (iframe API postMessage)
- TorrentAdapter (WebTorrent blob URLs)

## Data Model Changes

```sql
ALTER TABLE books ADD COLUMN source TEXT DEFAULT 'catalog';
ALTER TABLE tracks ADD COLUMN source_type TEXT DEFAULT 'file';
ALTER TABLE tracks ADD COLUMN source_url TEXT;
```

## Implementation Order

1. FileAdapter (extract from current usePlayer.ts)
2. YouTubeAdapter + paste URL flow
3. TorrentAdapter + magnet/file flow
4. Unified player switching between adapters
