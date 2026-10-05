package dev.pyfabric.client.radio;

import java.io.BufferedInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import javax.net.ssl.SSLSocketFactory;

/**
 * A tiny HTTP/1.0 client for internet radio. Java's HttpURLConnection can't be used because old
 * Shoutcast servers answer with a non-standard "ICY 200 OK" status line.
 */
final class RadioHttp {
	static final int CONNECT_TIMEOUT_MS = 10_000;
	static final int READ_TIMEOUT_MS = 15_000;

	private RadioHttp() {}

	/** An open response: headers (lower-case names) and the body stream. */
	record Response(URI uri, Socket socket, InputStream body, Map<String, String> headers) implements AutoCloseable {
		String header(String name) {
			return headers.get(name.toLowerCase(Locale.ROOT));
		}

		String contentType() {
			String ct = header("content-type");
			if (ct == null) return "";
			int semi = ct.indexOf(';');
			return (semi >= 0 ? ct.substring(0, semi) : ct).trim().toLowerCase(Locale.ROOT);
		}

		@Override
		public void close() {
			try {
				socket.close();
			} catch (IOException ignored) {
			}
		}
	}

	static Response get(URI uri) throws IOException {
		for (int redirect = 0; redirect < 6; redirect++) {
			String scheme = uri.getScheme() == null ? "" : uri.getScheme().toLowerCase(Locale.ROOT);
			if (!scheme.equals("http") && !scheme.equals("https")) {
				throw new IOException("Not an http(s) URL: " + uri);
			}
			boolean tls = scheme.equals("https");
			String host = uri.getHost();
			if (host == null) throw new IOException("No host in URL: " + uri);
			int port = uri.getPort() > 0 ? uri.getPort() : (tls ? 443 : 80);

			Socket socket = new Socket();
			try {
				socket.connect(new InetSocketAddress(host, port), CONNECT_TIMEOUT_MS);
				if (tls) socket = ((SSLSocketFactory) SSLSocketFactory.getDefault()).createSocket(socket, host, port, true);
				socket.setSoTimeout(READ_TIMEOUT_MS);

				String path = uri.getRawPath() == null || uri.getRawPath().isEmpty() ? "/" : uri.getRawPath();
				if (uri.getRawQuery() != null) path += "?" + uri.getRawQuery();
				String hostHeader = uri.getPort() > 0 ? host + ":" + port : host;
				String request = "GET " + path + " HTTP/1.0\r\n"
						+ "Host: " + hostHeader + "\r\n"
						+ "User-Agent: PyFabric-Radio/1.0\r\n"
						+ "Accept: */*\r\n"
						+ "Icy-MetaData: 1\r\n"
						+ "Connection: close\r\n\r\n";
				OutputStream out = socket.getOutputStream();
				out.write(request.getBytes(StandardCharsets.ISO_8859_1));
				out.flush();

				InputStream in = new BufferedInputStream(socket.getInputStream(), 64 * 1024);
				String status = readLine(in);
				if (status == null) throw new IOException("Server closed the connection");
				String[] parts = status.split(" ", 3);
				int code;
				try {
					code = Integer.parseInt(parts.length > 1 ? parts[1] : "");
				} catch (NumberFormatException e) {
					throw new IOException("Not an HTTP/Icecast/Shoutcast response: " + status);
				}
				Map<String, String> headers = new HashMap<>();
				String line;
				while ((line = readLine(in)) != null && !line.isEmpty()) {
					int colon = line.indexOf(':');
					if (colon > 0) headers.put(line.substring(0, colon).trim().toLowerCase(Locale.ROOT), line.substring(colon + 1).trim());
				}
				if (code >= 300 && code < 400 && headers.containsKey("location")) {
					socket.close();
					uri = uri.resolve(headers.get("location"));
					continue;
				}
				if (code != 200) throw new IOException("Server answered " + status.trim());
				return new Response(uri, socket, in, headers);
			} catch (IOException | RuntimeException e) {
				socket.close();
				throw e;
			}
		}
		throw new IOException("Too many redirects");
	}

	/** Reads a CRLF/LF terminated line (ISO-8859-1), or null at end of stream. */
	static String readLine(InputStream in) throws IOException {
		ByteArrayOutputStream buf = new ByteArrayOutputStream();
		int b;
		while ((b = in.read()) != -1) {
			if (b == '\n') break;
			if (buf.size() > 16 * 1024) throw new IOException("Header line too long");
			buf.write(b);
		}
		if (b == -1 && buf.size() == 0) return null;
		String s = buf.toString(StandardCharsets.ISO_8859_1);
		return s.endsWith("\r") ? s.substring(0, s.length() - 1) : s;
	}

	/** Reads at most {@code limit} bytes of a (small) body, e.g. a playlist file. */
	static String readSmallBody(InputStream in, int limit) throws IOException {
		ByteArrayOutputStream buf = new ByteArrayOutputStream();
		byte[] chunk = new byte[4096];
		int n;
		while (buf.size() < limit && (n = in.read(chunk)) != -1) buf.write(chunk, 0, n);
		return buf.toString(StandardCharsets.UTF_8);
	}
}
