package dev.pyfabric.client.radio;

import java.io.FilterInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.function.Consumer;

/**
 * Removes Icecast/Shoutcast ("ICY") metadata blocks from an audio stream and reports the stream titles.
 *
 * <p>With {@code Icy-MetaData: 1}, the server inserts a metadata block after every {@code icy-metaint} bytes
 * of audio: one length byte (times 16) followed by text like {@code StreamTitle='Artist - Song';}.
 */
final class IcyInputStream extends FilterInputStream {
	private final int metaInt;
	private final Consumer<String> titleListener;
	private int untilMeta;
	private String lastTitle;

	IcyInputStream(InputStream in, int metaInt, Consumer<String> titleListener) {
		super(in);
		this.metaInt = metaInt;
		this.untilMeta = metaInt;
		this.titleListener = titleListener;
	}

	@Override
	public int read() throws IOException {
		byte[] one = new byte[1];
		int n = read(one, 0, 1);
		return n == -1 ? -1 : one[0] & 0xFF;
	}

	@Override
	public int read(byte[] b, int off, int len) throws IOException {
		if (len == 0) return 0;
		if (untilMeta == 0) {
			readMetadata();
			untilMeta = metaInt;
		}
		int n = in.read(b, off, Math.min(len, untilMeta));
		if (n > 0) untilMeta -= n;
		return n;
	}

	@Override
	public long skip(long n) throws IOException {
		byte[] tmp = new byte[(int) Math.min(n, 8192)];
		int r = read(tmp, 0, tmp.length);
		return Math.max(r, 0);
	}

	@Override
	public boolean markSupported() {
		return false;
	}

	private void readMetadata() throws IOException {
		int lenByte = in.read();
		if (lenByte == -1) return;
		int length = lenByte * 16;
		if (length == 0) return;
		byte[] meta = in.readNBytes(length);
		if (meta.length < length) return;
		String text = decode(meta);
		String title = parseTitle(text);
		if (title != null && !title.equals(lastTitle)) {
			lastTitle = title;
			titleListener.accept(title);
		}
	}

	/** Extracts StreamTitle='...'; (titles may themselves contain apostrophes). */
	static String parseTitle(String meta) {
		int start = meta.indexOf("StreamTitle='");
		if (start < 0) return null;
		start += "StreamTitle='".length();
		int end = meta.indexOf("';", start);
		if (end < 0) {
			end = meta.lastIndexOf('\'');
			if (end < start) end = meta.length();
		}
		String title = meta.substring(start, end).trim();
		return title.isEmpty() ? null : title;
	}

	/** Metadata is usually UTF-8, but old servers send Latin-1. */
	private static String decode(byte[] bytes) {
		int len = bytes.length;
		while (len > 0 && bytes[len - 1] == 0) len--;
		try {
			return StandardCharsets.UTF_8.newDecoder()
					.onMalformedInput(CodingErrorAction.REPORT)
					.onUnmappableCharacter(CodingErrorAction.REPORT)
					.decode(ByteBuffer.wrap(bytes, 0, len)).toString();
		} catch (CharacterCodingException e) {
			return new String(bytes, 0, len, StandardCharsets.ISO_8859_1);
		}
	}
}
