package com.leerio.app;

import android.Manifest;
import android.os.Build;
import com.getcapacitor.JSObject;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;

/**
 * Android 13+ hides other apps' audio files in shared storage (e.g. /sdcard/Audiobooks)
 * unless READ_MEDIA_AUDIO is granted. @capacitor/filesystem reports "granted" on 13+
 * without asking for it, so the folder scanner saw empty book folders.
 */
@CapacitorPlugin(
    name = "AudioPermission",
    permissions = { @Permission(strings = { Manifest.permission.READ_MEDIA_AUDIO }, alias = "audio") }
)
public class AudioPermissionPlugin extends Plugin {

    @PluginMethod
    public void request(PluginCall call) {
        // Below Android 13 READ_EXTERNAL_STORAGE (requested by Filesystem) covers audio files
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU || getPermissionState("audio") == PermissionState.GRANTED) {
            resolve(call, true);
            return;
        }
        requestPermissionForAlias("audio", call, "audioCallback");
    }

    @PermissionCallback
    private void audioCallback(PluginCall call) {
        resolve(call, getPermissionState("audio") == PermissionState.GRANTED);
    }

    private void resolve(PluginCall call, boolean granted) {
        JSObject ret = new JSObject();
        ret.put("granted", granted);
        call.resolve(ret);
    }
}
