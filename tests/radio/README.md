# Radio tests

Tests the stream player (`src/client/java/dev/pyfabric/client/radio`) against a fake Icecast/Shoutcast
server, without Minecraft or a sound card:

```bash
cd tests/radio
ffmpeg -f lavfi -i "sine=frequency=440:duration=20" -ac 2 -ar 44100 -b:a 128k tone.mp3
python3 fake_icecast.py 8790 &
JL=~/.gradle/caches/modules-2/files-2.1/com.googlecode.soundlibs/jlayer/1.0.1.4/*/jlayer-1.0.1.4.jar
javac -encoding UTF-8 -d out -cp $JL ../../src/client/java/dev/pyfabric/client/radio/*.java RadioTest.java
java -cp out:$JL RadioTest 8790
```

Covers Icecast and Shoutcast v1 (`ICY 200 OK`) responses, ICY metadata titles (UTF-8, apostrophes),
station names, volume scaling, redirects, `.pls` playlists, reconnecting after drops, and clear errors for
AAC, HLS and bad URLs.

In-game, `-Dpyfabric.radio.sink=null` decodes without a sound card (for headless testing).
