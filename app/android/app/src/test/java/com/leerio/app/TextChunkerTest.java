package com.leerio.app;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import java.util.List;
import org.junit.Test;

public class TextChunkerTest {

    @Test
    public void shortTextIsOneChunk() {
        assertEquals(List.of("Привіт."), TextChunker.split("  Привіт.  ", 100));
    }

    @Test
    public void chunksRespectLimitAndKeepAllWords() {
        String text = "Перше речення тут. Друге речення довше за перше! Третє? Четверте речення.\n".repeat(200);
        List<String> chunks = TextChunker.split(text, 3000);
        assertTrue(chunks.size() > 1);
        StringBuilder joined = new StringBuilder();
        for (String c : chunks) {
            assertTrue(c.length() <= 3000);
            joined.append(c).append(' ');
        }
        assertEquals(text.split("\\s+").length, joined.toString().trim().split("\\s+").length);
    }

    @Test
    public void cutsAtParagraphThenSentenceThenSpace() {
        assertEquals(List.of("aaaa bbbb", "cccc"), TextChunker.split("aaaa bbbb\ncccc", 12));
        assertEquals(List.of("Один два.", "Три чотири"), TextChunker.split("Один два. Три чотири", 14));
        assertEquals(List.of("один два", "три"), TextChunker.split("один два три", 10));
    }

    @Test
    public void hardCutWithoutSpaces() {
        assertEquals(List.of("abcde", "fghij", "k"), TextChunker.split("abcdefghijk", 5));
    }
}
