"""Fake internet radio server for testing: Icecast (HTTP/1.0) and Shoutcast v1 (ICY 200 OK) with ICY metadata."""
import socket, threading, sys, time

MP3 = open("tone.mp3", "rb").read()
METAINT = 8192
TITLES = ["Artist One - First Song", "Café Tacvba - Ojalá que llueva café", "It's a 'quoted' title"]
stats = {"connections": 0}

def meta_block(title):
    text = f"StreamTitle='{title}';StreamUrl='';".encode("utf-8")
    n = (len(text) + 15) // 16
    return bytes([n]) + text.ljust(n * 16, b"\0")

def handle(conn):
    stats["connections"] += 1
    req = b""
    while b"\r\n\r\n" not in req:
        chunk = conn.recv(4096)
        if not chunk: return
        req += chunk
    first = req.split(b"\r\n")[0].decode()
    path = first.split()[1]
    wants_meta = b"icy-metadata: 1" in req.lower()
    def send(s): conn.sendall(s)
    if path == "/redirect":
        send(b"HTTP/1.1 302 Found\r\nLocation: /stream.pls\r\nContent-Length: 0\r\n\r\n"); return
    if path == "/stream.pls":
        body = b"[playlist]\nNumberOfEntries=1\nFile1=http://127.0.0.1:%d/shoutcast\nTitle1=Test\nLength1=-1\nVersion=2\n" % PORT
        send(b"HTTP/1.0 200 OK\r\nContent-Type: audio/x-scpls\r\n\r\n" + body); return
    if path == "/hls.m3u8":
        send(b"HTTP/1.0 200 OK\r\nContent-Type: application/vnd.apple.mpegurl\r\n\r\n#EXTM3U\n#EXT-X-VERSION:3\nseg1.ts\n"); return
    if path == "/aac":
        send(b"HTTP/1.0 200 OK\r\nContent-Type: audio/aacp\r\n\r\n" + b"\0" * 1000); return
    if path == "/notfound":
        send(b"HTTP/1.0 404 Not Found\r\n\r\n"); return
    if path.startswith("/shoutcast"):
        head = b"ICY 200 OK\r\nicy-name:Fake Shoutcast FM\r\ncontent-type:audio/mpeg\r\n"
    else:
        head = b"HTTP/1.0 200 OK\r\nContent-Type: audio/mpeg\r\nicy-name: Fake Icecast Radio\r\n"
    if wants_meta:
        head += b"icy-metaint: %d\r\n" % METAINT
    send(head + b"\r\n")
    drop_after = int(path.split("drop=")[1]) if "drop=" in path else None
    pos, sent, ti = 0, 0, 0
    try:
        while True:
            block = MP3[pos:pos + METAINT]
            if len(block) < METAINT:
                pos = 0; continue
            pos += METAINT
            send(block)
            sent += len(block)
            if wants_meta:
                # change title every ~4 blocks; send empty metadata otherwise
                if (sent // METAINT) % 4 == 1:
                    send(meta_block(TITLES[ti % len(TITLES)])); ti += 1
                else:
                    send(b"\0")
            if drop_after and sent >= drop_after:
                return       # simulate the connection dropping
            time.sleep(METAINT / 16000 * 0.5)   # ~2x real time (128 kbps = 16 kB/s)
    except OSError:
        pass

PORT = int(sys.argv[1])
srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("127.0.0.1", PORT)); srv.listen()
while True:
    c, _ = srv.accept()
    threading.Thread(target=lambda: (handle(c), c.close()), daemon=True).start()
