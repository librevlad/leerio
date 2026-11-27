package com.leerio.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.database.Cursor;
import android.media.MediaScannerConnection;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.IBinder;
import android.os.PowerManager;
import android.os.SystemClock;
import android.provider.MediaStore;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.Voice;
import android.util.Log;
import androidx.core.app.NotificationCompat;
import androidx.core.app.ServiceCompat;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * Narrates a book with the phone's own TTS engine: chapter text → WAV pieces → AAC in .m4a
 * → Audiobooks/&lt;Author - Title&gt;/NN Title.m4a in shared storage.
 * Runs in the foreground so it keeps going with the screen off or the app in the background.
 * The job comes from {@link NarrationPlugin} as a JSON file; progress goes back as events and status.json.
 */
public class NarrationService extends Service {

    static final String ACTION_CANCEL = "com.leerio.app.narration.CANCEL";
    static final String EXTRA_TITLE = "title";
    static final String EXTRA_LABELS = "labels";

    private static final String TAG = "Narration";
    private static final String CHANNEL_ID = "narration";
    private static final int NOTIFICATION_ID = 7301;
    private static final int DONE_NOTIFICATION_ID = 7302;
    private static final int CHUNK_LIMIT = 3000;
    private static final long CHUNK_TIMEOUT_MS = 5 * 60_000L;

    interface Listener {
        void onNarrationEvent(String event, JSONObject status);
    }

    private static volatile Listener listener;
    /** Set by the plugin before the service starts, cleared when the job ends. */
    private static volatile boolean active;
    private static volatile boolean cancelRequested;
    /** Why the system stopped us early: "timeout" (Android 15+ time budget) or "interrupted" */
    private static volatile String stopCode;

    private Thread worker;
    private PowerManager.WakeLock wakeLock;
    private NotificationManager notifications;
    private String bookTitle = "";
    private JSONObject labels = new JSONObject();

    static void setListener(Listener l) {
        listener = l;
    }

    static boolean isActive() {
        return active;
    }

    static void markActive(boolean value) {
        active = value;
    }

    static void requestCancel() {
        cancelRequested = true;
    }

    // ── Job and status files ────────────────────────────────────────────

    private static File stateDir(Context c) {
        File d = new File(c.getFilesDir(), "narration");
        if (!d.exists() && !d.mkdirs()) Log.w(TAG, "Cannot create " + d);
        return d;
    }

    static File jobFile(Context c) {
        return new File(stateDir(c), "job.json");
    }

    private static File statusFile(Context c) {
        return new File(stateDir(c), "status.json");
    }

    static JSONObject readStatus(Context c) {
        try {
            return new JSONObject(readText(statusFile(c)));
        } catch (IOException | JSONException e) {
            JSONObject idle = new JSONObject();
            try {
                idle.put("state", "idle");
            } catch (JSONException ignored) {
                // Constant key
            }
            return idle;
        }
    }

    static void saveStatus(Context c, JSONObject status) {
        try {
            writeText(statusFile(c), status.toString());
        } catch (IOException e) {
            Log.w(TAG, "Cannot save status", e);
        }
    }

    static void clearStatus(Context c) {
        if (!statusFile(c).delete()) Log.d(TAG, "No status to clear");
    }

    /** Plain streams, not java.nio.file: that only exists from Android 8, the app runs from Android 7 */
    static String readText(File f) throws IOException {
        try (InputStream in = new FileInputStream(f); ByteArrayOutputStream buf = new ByteArrayOutputStream()) {
            byte[] chunk = new byte[8192];
            for (int n; (n = in.read(chunk)) != -1; ) buf.write(chunk, 0, n);
            return new String(buf.toByteArray(), StandardCharsets.UTF_8);
        }
    }

    /**
     * Writes the whole file or nothing: a temp file renamed over the old one. A process killed
     * mid-write leaves the previous status, not a cut JSON that reads as "idle" (job lost).
     */
    static void writeText(File f, String text) throws IOException {
        File tmp = new File(f.getPath() + ".tmp");
        try (OutputStream out = new FileOutputStream(tmp)) {
            out.write(text.getBytes(StandardCharsets.UTF_8));
        }
        // rename(2) on the same disk replaces the old file in one step
        if (!tmp.renameTo(f)) throw new IOException("Cannot replace " + f.getName());
    }

    /** "Audiobooks/A - T" → "Audiobooks/A - T (2)" when the folder is already there. */
    static String uniqueDir(String rel) {
        File root = Environment.getExternalStorageDirectory();
        String candidate = rel;
        for (int n = 2; new File(root, candidate).exists(); n++) candidate = rel + " (" + n + ")";
        return candidate;
    }

    // ── Service ─────────────────────────────────────────────────────────

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_CANCEL.equals(intent.getAction())) {
            cancelRequested = true;
            if (worker == null) stopSelf();
            return START_NOT_STICKY;
        }
        notifications = getSystemService(NotificationManager.class);
        if (intent != null) {
            bookTitle = intent.getStringExtra(EXTRA_TITLE) != null ? intent.getStringExtra(EXTRA_TITLE) : "";
            try {
                String raw = intent.getStringExtra(EXTRA_LABELS);
                if (raw != null) labels = new JSONObject(raw);
            } catch (JSONException ignored) {
                // Defaults below
            }
        }
        createChannel();
        Notification first = progressNotification(label("starting", "…"), 0, true);
        // Not ServiceCompat: it masks the type to the API 34 set and turns mediaProcessing into "none"
        if (Build.VERSION.SDK_INT >= 35) {
            startForeground(NOTIFICATION_ID, first, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROCESSING);
        } else if (Build.VERSION.SDK_INT >= 29) {
            startForeground(NOTIFICATION_ID, first, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
        } else {
            startForeground(NOTIFICATION_ID, first);
        }

        if (worker != null) return START_NOT_STICKY;
        cancelRequested = false;
        stopCode = null;
        PowerManager pm = getSystemService(PowerManager.class);
        wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "leerio:narration");
        wakeLock.acquire(6 * 60 * 60 * 1000L);
        worker = new Thread(this::work, "narration");
        worker.start();
        return START_NOT_STICKY;
    }

    /** Android 15+: the media-processing time budget is used up — stop, keeping finished chapters. */
    @Override
    public void onTimeout(int startId, int fgsType) {
        stopCode = "timeout";
    }

    @Override
    public void onDestroy() {
        if (worker != null && worker.isAlive() && stopCode == null) stopCode = "interrupted";
        super.onDestroy();
    }

    // ── Work ────────────────────────────────────────────────────────────

    private void work() {
        JSONObject status = new JSONObject();
        List<Object> created = new ArrayList<>(); // MediaStore Uris (API 29+) or Files
        TextToSpeech tts = null;
        boolean ok = false;
        try {
            JSONObject job = new JSONObject(readText(jobFile(this)));
            String dir = job.getString("dir");
            JSONArray chapters = job.getJSONArray("chapters");
            int total = chapters.length();
            JSONArray files = new JSONArray();
            status.put("state", "running").put("dir", dir).put("title", job.optString("title"))
                .put("author", job.optString("author")).put("total", total).put("current", 0)
                .put("progress", 0).put("files", files);
            saveStatus(this, status);

            tts = initTts(job.optString("engine", ""));
            applyVoice(tts, job.optString("voice", ""), job.optString("lang", ""));
            Synth synth = new Synth(tts);

            long totalChars = 0;
            for (int i = 0; i < total; i++) totalChars += chapters.getJSONObject(i).getString("text").length();
            long doneChars = 0;
            int limit = Math.min(CHUNK_LIMIT, TextToSpeech.getMaxSpeechInputLength() - 1);
            File workDir = new File(getCacheDir(), "narration");
            if (!workDir.exists() && !workDir.mkdirs()) throw new NarrationException("storage");
            File wav = new File(workDir, "chunk.wav");
            File m4a = new File(workDir, "chapter.m4a");

            for (int i = 0; i < total; i++) {
                JSONObject ch = chapters.getJSONObject(i);
                String text = ch.getString("text");
                status.put("current", i);
                emit("progress", status);
                updateProgress(status);

                M4aWriter writer = new M4aWriter(m4a);
                long durationUs;
                try {
                    for (String chunk : TextChunker.split(text, limit)) {
                        checkStop();
                        synth.toFile(chunk, wav);
                        writer.appendWav(wav);
                        doneChars += chunk.length();
                        status.put("progress", Math.min(1.0, (double) doneChars / Math.max(1, totalChars)));
                        emit("progress", status);
                        updateProgress(status);
                    }
                    checkStop();
                    durationUs = writer.finish();
                } finally {
                    writer.release();
                    deleteQuietly(wav);
                }
                long size = m4a.length();
                String path = publish(m4a, dir, ch.getString("file"), created);
                deleteQuietly(m4a);

                files.put(new JSONObject().put("index", i).put("title", ch.optString("title"))
                    .put("path", path).put("durationMs", durationUs / 1000).put("size", size));
                saveStatus(this, status);
                emit("chapterDone", status);
            }
            status.put("state", "done").put("progress", 1);
            saveStatus(this, status);
            ok = true;
            emit("finished", status);
        } catch (CancelledException e) {
            for (Object item : created) deleteCreated(item);
            // The now empty book folder
            deleteQuietly(new File(Environment.getExternalStorageDirectory(), status.optString("dir", "-")));
            putQuietly(status, "state", "cancelled");
            putQuietly(status, "files", new JSONArray());
            saveStatus(this, status);
            emit("error", status);
        } catch (Exception e) {
            Log.e(TAG, "Narration failed", e);
            putQuietly(status, "state", "error");
            putQuietly(status, "error", e instanceof NarrationException ? e.getMessage() : "failed");
            saveStatus(this, status);
            emit("error", status);
        } finally {
            if (tts != null) tts.shutdown();
            deleteQuietly(jobFile(this));
            if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
            active = false;
            worker = null;
            ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE);
            if (!"cancelled".equals(status.optString("state"))) showDone(ok);
            stopSelf();
        }
    }

    private void checkStop() throws NarrationException {
        if (cancelRequested) throw new CancelledException();
        String code = stopCode;
        if (code != null) throw new NarrationException(code);
    }

    private void emit(String event, JSONObject status) {
        Listener l = listener;
        if (l != null) l.onNarrationEvent(event, status);
    }

    private TextToSpeech initTts(String engine) throws Exception {
        CountDownLatch latch = new CountDownLatch(1);
        int[] result = { TextToSpeech.ERROR };
        TextToSpeech tts = new TextToSpeech(
            getApplicationContext(),
            s -> {
                result[0] = s;
                latch.countDown();
            },
            engine.isEmpty() ? null : engine
        );
        if (!latch.await(30, TimeUnit.SECONDS) || result[0] != TextToSpeech.SUCCESS) {
            tts.shutdown();
            throw new NarrationException("no_engine");
        }
        return tts;
    }

    private static void applyVoice(TextToSpeech tts, String voiceName, String lang) throws NarrationException {
        if (!voiceName.isEmpty()) {
            Set<Voice> voices = tts.getVoices();
            if (voices != null) {
                for (Voice v : voices) {
                    if (v.getName().equals(voiceName) && tts.setVoice(v) == TextToSpeech.SUCCESS) return;
                }
            }
        }
        if (!lang.isEmpty() && tts.setLanguage(Locale.forLanguageTag(lang)) < 0) throw new NarrationException("no_voice");
    }

    /** Waits for one synthesizeToFile call, checking for cancel twice a second. */
    private final class Synth extends UtteranceProgressListener {
        private final TextToSpeech tts;
        private volatile String waitingId;
        private volatile CountDownLatch latch;
        private volatile boolean failed;
        private int counter;

        Synth(TextToSpeech tts) {
            this.tts = tts;
            tts.setOnUtteranceProgressListener(this);
        }

        void toFile(String text, File out) throws Exception {
            String id = "n" + ++counter;
            latch = new CountDownLatch(1);
            failed = false;
            waitingId = id;
            deleteQuietly(out);
            if (tts.synthesizeToFile(text, new Bundle(), out, id) != TextToSpeech.SUCCESS) {
                throw new NarrationException("synthesis");
            }
            // Monotonic clock: a wall-clock change (time zone, manual time, network sync) must not
            // cut synthesis short or stretch the wait
            long deadline = SystemClock.elapsedRealtime() + CHUNK_TIMEOUT_MS;
            while (!latch.await(500, TimeUnit.MILLISECONDS)) {
                if (cancelRequested || stopCode != null) tts.stop();
                checkStop();
                if (SystemClock.elapsedRealtime() > deadline) throw new NarrationException("synthesis");
            }
            if (failed) throw new NarrationException("synthesis");
        }

        @Override
        public void onStart(String utteranceId) {}

        @Override
        public void onDone(String utteranceId) {
            if (utteranceId.equals(waitingId)) latch.countDown();
        }

        @Override
        @Deprecated
        public void onError(String utteranceId) {
            onError(utteranceId, TextToSpeech.ERROR);
        }

        @Override
        public void onError(String utteranceId, int errorCode) {
            if (!utteranceId.equals(waitingId)) return;
            failed = true;
            latch.countDown();
        }
    }

    // ── Shared storage ──────────────────────────────────────────────────

    /** Copies a finished chapter to Audiobooks/…; returns its path relative to external storage. */
    private String publish(File src, String relDir, String fileName, List<Object> created) throws NarrationException {
        try {
            if (Build.VERSION.SDK_INT >= 29) {
                ContentResolver resolver = getContentResolver();
                ContentValues v = new ContentValues();
                v.put(MediaStore.MediaColumns.DISPLAY_NAME, fileName);
                v.put(MediaStore.MediaColumns.MIME_TYPE, "audio/mp4");
                v.put(MediaStore.MediaColumns.RELATIVE_PATH, relDir + "/");
                v.put(MediaStore.MediaColumns.IS_PENDING, 1);
                Uri uri = resolver.insert(MediaStore.Audio.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY), v);
                if (uri == null) throw new IOException("MediaStore insert failed");
                created.add(uri);
                try (InputStream in = new FileInputStream(src); OutputStream out = resolver.openOutputStream(uri)) {
                    if (out == null) throw new IOException("No output stream");
                    copy(in, out);
                }
                v.clear();
                v.put(MediaStore.MediaColumns.IS_PENDING, 0);
                resolver.update(uri, v, null, null);
                // MediaStore may adjust the name: read back what it stored
                String[] cols = { MediaStore.MediaColumns.RELATIVE_PATH, MediaStore.MediaColumns.DISPLAY_NAME };
                try (Cursor c = resolver.query(uri, cols, null, null, null)) {
                    if (c != null && c.moveToFirst()) {
                        String rel = c.getString(0);
                        if (!rel.endsWith("/")) rel += "/";
                        return rel + c.getString(1);
                    }
                }
                return relDir + "/" + fileName;
            }
            File dir = new File(Environment.getExternalStorageDirectory(), relDir);
            if (!dir.exists() && !dir.mkdirs()) throw new IOException("Cannot create " + dir);
            File dst = new File(dir, fileName);
            created.add(dst);
            try (InputStream in = new FileInputStream(src); OutputStream out = new FileOutputStream(dst)) {
                copy(in, out);
            }
            MediaScannerConnection.scanFile(this, new String[] { dst.getPath() }, null, null);
            return relDir + "/" + fileName;
        } catch (IOException | RuntimeException e) {
            Log.e(TAG, "Cannot save chapter", e);
            throw new NarrationException("storage");
        }
    }

    private void deleteCreated(Object item) {
        try {
            if (item instanceof Uri) getContentResolver().delete((Uri) item, null, null);
            else if (item instanceof File) deleteQuietly((File) item);
        } catch (RuntimeException e) {
            Log.w(TAG, "Cannot delete " + item, e);
        }
    }

    private static void copy(InputStream in, OutputStream out) throws IOException {
        byte[] buf = new byte[65536];
        int n;
        while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
    }

    private static void deleteQuietly(File f) {
        if (f.exists() && !f.delete()) Log.w(TAG, "Cannot delete " + f);
    }

    private static void putQuietly(JSONObject o, String key, Object value) {
        try {
            o.put(key, value);
        } catch (JSONException ignored) {
            // Non-null key
        }
    }

    // ── Notifications ───────────────────────────────────────────────────

    private String label(String key, String fallback) {
        String s = labels.optString(key, "");
        return s.isEmpty() ? fallback : s;
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT < 26) return;
        NotificationChannel channel = new NotificationChannel(
            CHANNEL_ID,
            label("channel", "Narration"),
            NotificationManager.IMPORTANCE_LOW
        );
        notifications.createNotificationChannel(channel);
    }

    private PendingIntent openAppIntent() {
        Intent open = getPackageManager().getLaunchIntentForPackage(getPackageName());
        if (open == null) open = new Intent(this, MainActivity.class);
        open.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        return PendingIntent.getActivity(this, 0, open, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    private Notification progressNotification(String text, int percent, boolean indeterminate) {
        Intent cancel = new Intent(this, NarrationService.class).setAction(ACTION_CANCEL);
        PendingIntent cancelIntent = PendingIntent.getService(
            this,
            1,
            cancel,
            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT
        );
        return new NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_narration)
            .setContentTitle(bookTitle)
            .setContentText(text)
            .setProgress(100, percent, indeterminate)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setSilent(true)
            .setContentIntent(openAppIntent())
            .addAction(0, label("cancel", "Cancel"), cancelIntent)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
            .build();
    }

    private void updateProgress(JSONObject status) {
        String text = label("progress", "{current} / {total}")
            .replace("{current}", String.valueOf(status.optInt("current") + 1))
            .replace("{total}", String.valueOf(status.optInt("total")));
        int percent = (int) Math.round(status.optDouble("progress", 0) * 100);
        notifications.notify(NOTIFICATION_ID, progressNotification(text, percent, false));
    }

    private void showDone(boolean ok) {
        Notification n = new NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_narration)
            .setContentTitle(bookTitle)
            .setContentText(ok ? label("done", "Done") : label("failed", "Failed"))
            .setAutoCancel(true)
            .setContentIntent(openAppIntent())
            .build();
        notifications.notify(DONE_NOTIFICATION_ID, n);
    }

    // ── Errors ──────────────────────────────────────────────────────────

    /** Message is an error code the JS side translates: no_engine, no_voice, synthesis, storage, timeout. */
    static class NarrationException extends Exception {
        NarrationException(String code) {
            super(code);
        }
    }

    static final class CancelledException extends NarrationException {
        CancelledException() {
            super("cancelled");
        }
    }
}
