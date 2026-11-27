package com.leerio.app;

import java.util.ArrayList;
import java.util.List;

/** Cuts chapter text into pieces a TTS engine accepts in one synthesizeToFile call. */
final class TextChunker {

    private TextChunker() {}

    static List<String> split(String text, int max) {
        List<String> out = new ArrayList<>();
        int i = 0;
        int n = text.length();
        while (i < n) {
            int end = Math.min(n, i + max);
            if (end < n) end = breakPoint(text, i, end);
            String part = text.substring(i, end).trim();
            if (!part.isEmpty()) out.add(part);
            i = end;
        }
        return out;
    }

    /** Best cut inside text[from, limit): paragraph, then sentence end, then space — never in the first third. */
    private static int breakPoint(String text, int from, int limit) {
        int min = from + (limit - from) / 3;
        int nl = text.lastIndexOf('\n', limit - 1);
        if (nl >= min) return nl + 1;
        for (int j = limit - 1; j >= min; j--) {
            char c = text.charAt(j);
            boolean sentenceEnd = c == '.' || c == '!' || c == '?' || c == '…' || c == ';';
            if (sentenceEnd && j + 1 < text.length() && Character.isWhitespace(text.charAt(j + 1))) return j + 1;
        }
        int sp = text.lastIndexOf(' ', limit - 1);
        if (sp >= min) return sp + 1;
        return limit;
    }
}
