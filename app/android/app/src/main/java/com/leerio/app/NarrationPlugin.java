package com.leerio.app;

import android.Manifest;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.speech.tts.TextToSpeech;
import android.speech.tts.Voice;
import androidx.core.content.ContextCompat;
import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * On-device book narration (see {@link NarrationService}): installed TTS voices, voice preview,
 * start / cancel / status of the narration job. Events: progress, chapterDone, finished, error —
 * each carries the whole job status.
 */
@CapacitorPlugin(
    name = "Narration",
    permissions = {
        @Permission(strings = { Manifest.permission.POST_NOTIFICATIONS }, alias = "notifications"),
        @Permission(strings = { Manifest.permission.WRITE_EXTERNAL_STORAGE }, alias = "storage"),
    }
)
public class NarrationPlugin extends Plugin implements NarrationService.Listener {

    private static final long VOICES_TIMEOUT_MS = 10_000;

    private TextToSpeech previewTts;
    private String previewEngine = "";
    private boolean previewReady;
    private Runnable pendingPreview;

    @Override
    public void load() {
        NarrationService.setListener(this);
    }

    @Override
    protected void handleOnDestroy() {
        NarrationService.setListener(null);
        shutdownPreview();
    }

    @Override
    public void onNarrationEvent(String event, JSONObject status) {
        try {
            notifyListeners(event, JSObject.fromJSONObject(status));
        } catch (JSONException ignored) {
            // Status is built from valid JSON
        }
    }

    // ── Voices ──────────────────────────────────────────────────────────

    /** Offline, installed voices of every TTS engine on the phone. */
    @PluginMethod
    public void getVoices(PluginCall call) {
        Context ctx = getContext().getApplicationContext();
        PackageManager pm = ctx.getPackageManager();
        List<ResolveInfo> engines = pm.queryIntentServices(new Intent(TextToSpeech.Engine.INTENT_ACTION_TTS_SERVICE), 0);
        String defaultEngine = Settings.Secure.getString(ctx.getContentResolver(), Settings.Secure.TTS_DEFAULT_SYNTH);

        JSArray voices = new JSArray();
        JSObject ret = new JSObject();
        ret.put("defaultEngine", defaultEngine != null ? defaultEngine : "");
        ret.put("voices", voices);
        if (engines.isEmpty()) {
            call.resolve(ret);
            return;
        }

        AtomicInteger left = new AtomicInteger(engines.size());
        AtomicBoolean resolved = new AtomicBoolean(false);
        List<TextToSpeech> instances = new ArrayList<>();
        Runnable finish = () -> {
            if (!resolved.compareAndSet(false, true)) return;
            synchronized (instances) {
                for (TextToSpeech t : instances) t.shutdown();
            }
            call.resolve(ret);
        };
        new Handler(Looper.getMainLooper()).postDelayed(finish, VOICES_TIMEOUT_MS);

        for (ResolveInfo ri : engines) {
            String pkg = ri.serviceInfo.packageName;
            String label = ri.loadLabel(pm).toString();
            TextToSpeech[] holder = new TextToSpeech[1];
            TextToSpeech.OnInitListener onInit = status -> {
                TextToSpeech tts = holder[0];
                if (status == TextToSpeech.SUCCESS && tts != null && !resolved.get()) {
                    collectVoices(tts, pkg, label, voices);
                }
                if (left.decrementAndGet() == 0) finish.run();
            };
            holder[0] = new TextToSpeech(ctx, onInit, pkg);
            synchronized (instances) {
                instances.add(holder[0]);
            }
        }
    }

    private static void collectVoices(TextToSpeech tts, String engine, String label, JSArray out) {
        Set<Voice> voices;
        Voice def;
        try {
            voices = tts.getVoices();
            def = tts.getDefaultVoice();
        } catch (RuntimeException e) {
            return; // Engine died while listing
        }
        if (voices == null) return;
        synchronized (out) {
            for (Voice v : voices) {
                Set<String> features = v.getFeatures();
                if (v.isNetworkConnectionRequired()) continue;
                if (features != null && features.contains(TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED)) continue;
                JSObject o = new JSObject();
                o.put("id", engine + "/" + v.getName());
                o.put("engine", engine);
                o.put("engineLabel", label);
                o.put("name", v.getName());
                o.put("lang", v.getLocale().toLanguageTag());
                o.put("quality", v.getQuality());
                o.put("isDefault", def != null && def.getName().equals(v.getName()));
                out.put(o);
            }
        }
    }

    @PluginMethod
    public void preview(PluginCall call) {
        String engine = call.getString("engine", "");
        String voice = call.getString("voice", "");
        String text = call.getString("text", "");
        if (previewTts != null && !previewEngine.equals(engine)) shutdownPreview();
        pendingPreview = () -> speakPreview(voice, text);
        if (previewTts == null) {
            previewEngine = engine;
            previewReady = false;
            previewTts = new TextToSpeech(
                getContext().getApplicationContext(),
                status -> {
                    previewReady = status == TextToSpeech.SUCCESS;
                    Runnable r = pendingPreview;
                    pendingPreview = null;
                    if (previewReady && r != null) r.run();
                },
                engine.isEmpty() ? null : engine
            );
        } else if (previewReady) {
            pendingPreview = null;
            speakPreview(voice, text);
        }
        call.resolve();
    }

    private void speakPreview(String voiceName, String text) {
        TextToSpeech tts = previewTts;
        if (tts == null) return;
        Set<Voice> voices = tts.getVoices();
        if (voices != null) {
            for (Voice v : voices) {
                if (v.getName().equals(voiceName)) {
                    tts.setVoice(v);
                    break;
                }
            }
        }
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "preview");
    }

    @PluginMethod
    public void stopPreview(PluginCall call) {
        if (previewTts != null && previewReady) previewTts.stop();
        call.resolve();
    }

    private void shutdownPreview() {
        if (previewTts != null) previewTts.shutdown();
        previewTts = null;
        previewReady = false;
        pendingPreview = null;
    }

    /** System TTS settings: pick an engine, download voices (e.g. Ukrainian). */
    @PluginMethod
    public void openTtsSettings(PluginCall call) {
        Intent settings = new Intent("com.android.settings.TTS_SETTINGS").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            getContext().startActivity(settings);
        } catch (ActivityNotFoundException e) {
            try {
                Intent install = new Intent(TextToSpeech.Engine.ACTION_INSTALL_TTS_DATA).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                getContext().startActivity(install);
            } catch (ActivityNotFoundException ignored) {
                call.reject("unavailable");
                return;
            }
        }
        call.resolve();
    }

    // ── Job ─────────────────────────────────────────────────────────────

    /**
     * { dir: "Audiobooks/A - T", title, author, engine, voice, lang,
     *   chapters: [{ title, text, file }], labels: { channel, progress, cancel, done, failed } }
     * Resolves { dir } — the folder actually used (" (2)" added when it already exists).
     */
    @PluginMethod
    public void start(PluginCall call) {
        if (NarrationService.isActive()) {
            call.reject("busy", "busy");
            return;
        }
        JSArray chapters = call.getArray("chapters");
        String dir = call.getString("dir", "");
        if (chapters == null || chapters.length() == 0 || dir.isEmpty()) {
            call.reject("bad_request", "bad_request");
            return;
        }
        List<String> need = new ArrayList<>();
        if (Build.VERSION.SDK_INT >= 33 && getPermissionState("notifications") != PermissionState.GRANTED) need.add("notifications");
        if (Build.VERSION.SDK_INT < 29 && getPermissionState("storage") != PermissionState.GRANTED) need.add("storage");
        if (need.isEmpty()) startJob(call);
        else requestPermissionForAliases(need.toArray(new String[0]), call, "startAfterPermissions");
    }

    @PermissionCallback
    private void startAfterPermissions(PluginCall call) {
        // The progress notification is optional; writing below Android 10 is not
        if (Build.VERSION.SDK_INT < 29 && getPermissionState("storage") != PermissionState.GRANTED) {
            call.reject("storage", "storage");
            return;
        }
        startJob(call);
    }

    private void startJob(PluginCall call) {
        Context ctx = getContext();
        shutdownPreview();
        try {
            String dir = NarrationService.uniqueDir(call.getString("dir", ""));
            String title = call.getString("title", "");
            JSONObject job = new JSONObject();
            job.put("dir", dir);
            job.put("title", title);
            job.put("author", call.getString("author", ""));
            job.put("engine", call.getString("engine", ""));
            job.put("voice", call.getString("voice", ""));
            job.put("lang", call.getString("lang", ""));
            job.put("chapters", call.getArray("chapters"));
            NarrationService.writeText(NarrationService.jobFile(ctx), job.toString());

            JSObject status = new JSObject();
            status.put("state", "running");
            status.put("dir", dir);
            status.put("title", title);
            status.put("author", call.getString("author", ""));
            status.put("total", call.getArray("chapters").length());
            status.put("current", 0);
            status.put("progress", 0);
            status.put("files", new JSArray());
            NarrationService.saveStatus(ctx, status);

            Intent intent = new Intent(ctx, NarrationService.class);
            intent.putExtra(NarrationService.EXTRA_TITLE, title);
            intent.putExtra(NarrationService.EXTRA_LABELS, call.getObject("labels", new JSObject()).toString());
            NarrationService.markActive(true);
            ContextCompat.startForegroundService(ctx, intent);

            JSObject ret = new JSObject();
            ret.put("dir", dir);
            call.resolve(ret);
        } catch (Exception e) {
            NarrationService.markActive(false);
            call.reject("failed", "failed", e);
        }
    }

    @PluginMethod
    public void cancel(PluginCall call) {
        if (NarrationService.isActive()) NarrationService.requestCancel();
        call.resolve();
    }

    /** Last job status; a "running" job whose process died is reported as interrupted. */
    @PluginMethod
    public void getStatus(PluginCall call) {
        JSONObject status = NarrationService.readStatus(getContext());
        try {
            if ("running".equals(status.optString("state")) && !NarrationService.isActive()) {
                status.put("state", "error");
                status.put("error", "interrupted");
                NarrationService.saveStatus(getContext(), status);
            }
            call.resolve(JSObject.fromJSONObject(status));
        } catch (JSONException e) {
            call.reject("failed", e);
        }
    }

    /** JS took the finished book into the library. */
    @PluginMethod
    public void clearStatus(PluginCall call) {
        if (!NarrationService.isActive()) NarrationService.clearStatus(getContext());
        call.resolve();
    }
}
