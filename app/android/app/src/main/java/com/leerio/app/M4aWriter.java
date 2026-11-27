package com.leerio.app;

import android.media.MediaCodec;
import android.media.MediaCodecInfo;
import android.media.MediaFormat;
import android.media.MediaMuxer;
import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;

/**
 * Appends WAV pieces from the TTS engine to one AAC track in an .m4a file.
 * Each WAV is streamed through the encoder and can be deleted right after — no big WAV on disk.
 */
final class M4aWriter {

    private static final int BIT_RATE_PER_CHANNEL = 48_000;
    private static final long TIMEOUT_US = 10_000;

    private final MediaMuxer muxer;
    private final MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
    private MediaCodec codec;
    private int track = -1;
    private boolean muxerStarted;
    private int sampleRate;
    private int channels;
    private long frames;

    M4aWriter(File out) throws IOException {
        muxer = new MediaMuxer(out.getPath(), MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4);
    }

    /** Streams the PCM data of a WAV file (16-bit, 8-bit or float) into the encoder. */
    void appendWav(File wav) throws IOException {
        try (InputStream in = new BufferedInputStream(new FileInputStream(wav), 65536)) {
            byte[] header = new byte[12];
            if (!readFully(in, header) || !"RIFF".equals(ascii(header, 0)) || !"WAVE".equals(ascii(header, 8))) {
                throw new IOException("TTS output is not WAV");
            }
            int format = 1;
            int ch = 1;
            int rate = 0;
            int bits = 16;
            long dataSize;
            byte[] chunk = new byte[8];
            while (true) {
                if (!readFully(in, chunk)) return; // no data chunk: empty utterance
                String id = ascii(chunk, 0);
                long size = le32(chunk, 4) & 0xffffffffL;
                if ("fmt ".equals(id)) {
                    byte[] f = new byte[(int) size];
                    if (!readFully(in, f)) throw new IOException("Broken WAV header");
                    format = le16(f, 0);
                    ch = le16(f, 2);
                    rate = le32(f, 4);
                    bits = le16(f, 14);
                    if (format == 0xfffe && size >= 26) format = le16(f, 24); // WAVE_FORMAT_EXTENSIBLE
                    if ((size & 1) == 1) skipFully(in, 1);
                } else if ("data".equals(id)) {
                    // Streamed files may carry 0 / 0xFFFFFFFF: read to EOF then
                    dataSize = size == 0 || size == 0xffffffffL ? Long.MAX_VALUE : size;
                    break;
                } else {
                    skipFully(in, size + (size & 1));
                }
            }
            if (rate <= 0 || ch <= 0) throw new IOException("WAV without format");
            ensureEncoder(rate, ch);

            int inFrame = ch * Math.max(1, bits / 8);
            byte[] buf = new byte[16384 - 16384 % inFrame];
            long left = dataSize;
            while (left > 0) {
                int n = in.read(buf, 0, (int) Math.min(buf.length, left));
                if (n <= 0) break;
                // Keep whole frames: top up a short read
                while (n % inFrame != 0) {
                    int m = in.read(buf, n, inFrame - n % inFrame);
                    if (m <= 0) break;
                    n += m;
                }
                n -= n % inFrame;
                left -= n;
                byte[] pcm = toPcm16(buf, n, format, bits);
                queuePcm(pcm, format == 1 && bits == 16 ? n : pcm.length);
            }
        }
    }

    /** Finishes the file, returns its duration in microseconds. */
    long finish() throws IOException {
        if (codec == null) {
            // Nothing was spoken: half a second of silence keeps the file valid
            ensureEncoder(22050, 1);
            queuePcm(new byte[22050], 22050);
        }
        while (true) {
            int idx = codec.dequeueInputBuffer(TIMEOUT_US);
            if (idx >= 0) {
                codec.queueInputBuffer(idx, 0, 0, ptsUs(), MediaCodec.BUFFER_FLAG_END_OF_STREAM);
                break;
            }
            drain(false);
        }
        drain(true);
        muxer.stop();
        muxerStarted = false;
        return ptsUs();
    }

    void release() {
        if (codec != null) {
            try {
                codec.stop();
            } catch (RuntimeException ignored) {
                // Already stopped
            }
            codec.release();
            codec = null;
        }
        if (muxerStarted) {
            try {
                muxer.stop();
            } catch (RuntimeException ignored) {
                // Broken file is deleted by the caller
            }
        }
        muxer.release();
    }

    private void ensureEncoder(int rate, int ch) throws IOException {
        if (codec != null) {
            if (rate != sampleRate || ch != channels) throw new IOException("TTS audio format changed");
            return;
        }
        sampleRate = rate;
        channels = ch;
        MediaFormat format = MediaFormat.createAudioFormat(MediaFormat.MIMETYPE_AUDIO_AAC, rate, ch);
        format.setInteger(MediaFormat.KEY_AAC_PROFILE, MediaCodecInfo.CodecProfileLevel.AACObjectLC);
        format.setInteger(MediaFormat.KEY_BIT_RATE, BIT_RATE_PER_CHANNEL * ch);
        format.setInteger(MediaFormat.KEY_MAX_INPUT_SIZE, 16384);
        codec = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_AUDIO_AAC);
        codec.configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE);
        codec.start();
    }

    private void queuePcm(byte[] data, int len) throws IOException {
        int frame = 2 * channels;
        int off = 0;
        while (off < len) {
            int idx = codec.dequeueInputBuffer(TIMEOUT_US);
            if (idx >= 0) {
                ByteBuffer b = codec.getInputBuffer(idx);
                if (b == null) throw new IOException("No encoder buffer");
                b.clear();
                int n = Math.min(b.remaining(), len - off);
                n -= n % frame;
                if (n <= 0) throw new IOException("Encoder buffer too small");
                b.put(data, off, n);
                codec.queueInputBuffer(idx, 0, n, ptsUs(), 0);
                frames += n / frame;
                off += n;
            }
            drain(false);
        }
    }

    private void drain(boolean endOfStream) throws IOException {
        long giveUp = System.currentTimeMillis() + 10_000;
        while (true) {
            int idx = codec.dequeueOutputBuffer(info, endOfStream ? TIMEOUT_US : 0);
            if (idx == MediaCodec.INFO_TRY_AGAIN_LATER) {
                if (!endOfStream) return;
                if (System.currentTimeMillis() > giveUp) throw new IOException("Encoder stalled");
            } else if (idx == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                track = muxer.addTrack(codec.getOutputFormat());
                muxer.start();
                muxerStarted = true;
            } else if (idx >= 0) {
                ByteBuffer out = codec.getOutputBuffer(idx);
                if ((info.flags & MediaCodec.BUFFER_FLAG_CODEC_CONFIG) != 0) info.size = 0;
                if (info.size > 0 && muxerStarted && out != null) {
                    out.position(info.offset);
                    out.limit(info.offset + info.size);
                    muxer.writeSampleData(track, out, info);
                }
                codec.releaseOutputBuffer(idx, false);
                if ((info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) return;
            }
        }
    }

    private long ptsUs() {
        return frames * 1_000_000L / sampleRate;
    }

    /** 8-bit unsigned and 32-bit float PCM → 16-bit little-endian */
    private static byte[] toPcm16(byte[] buf, int n, int format, int bits) throws IOException {
        if (format == 1 && bits == 16) return buf;
        if (format == 1 && bits == 8) {
            byte[] out = new byte[n * 2];
            for (int i = 0; i < n; i++) {
                int s = ((buf[i] & 0xff) - 128) << 8;
                out[2 * i] = (byte) s;
                out[2 * i + 1] = (byte) (s >> 8);
            }
            return out;
        }
        if (format == 3 && bits == 32) {
            byte[] out = new byte[n / 2];
            for (int i = 0; i + 3 < n; i += 4) {
                float f = Float.intBitsToFloat(le32(buf, i));
                int s = (int) (Math.max(-1f, Math.min(1f, f)) * 32767);
                out[i / 2] = (byte) s;
                out[i / 2 + 1] = (byte) (s >> 8);
            }
            return out;
        }
        throw new IOException("Unsupported WAV format " + format + "/" + bits);
    }

    private static boolean readFully(InputStream in, byte[] b) throws IOException {
        int off = 0;
        while (off < b.length) {
            int n = in.read(b, off, b.length - off);
            if (n < 0) return false;
            off += n;
        }
        return true;
    }

    private static void skipFully(InputStream in, long n) throws IOException {
        while (n > 0) {
            long s = in.skip(n);
            if (s <= 0) {
                if (in.read() < 0) return;
                s = 1;
            }
            n -= s;
        }
    }

    private static String ascii(byte[] b, int off) {
        return new String(b, off, 4, java.nio.charset.StandardCharsets.US_ASCII);
    }

    private static int le16(byte[] b, int off) {
        return (b[off] & 0xff) | (b[off + 1] & 0xff) << 8;
    }

    private static int le32(byte[] b, int off) {
        return (b[off] & 0xff) | (b[off + 1] & 0xff) << 8 | (b[off + 2] & 0xff) << 16 | (b[off + 3] & 0xff) << 24;
    }
}
