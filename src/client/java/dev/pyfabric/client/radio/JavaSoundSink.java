package dev.pyfabric.client.radio;

import javax.sound.sampled.AudioFormat;
import javax.sound.sampled.AudioSystem;
import javax.sound.sampled.SourceDataLine;

/** Plays PCM through the system's default audio output (Java Sound). */
public final class JavaSoundSink implements RadioStream.Sink {
	private SourceDataLine line;

	@Override
	public void open(int sampleRate, int channels) throws Exception {
		AudioFormat format = new AudioFormat(sampleRate, 16, channels, true, false);
		SourceDataLine l = AudioSystem.getSourceDataLine(format);
		// ~0.5 s device buffer: small enough for quick volume changes, big enough to ride out hiccups
		l.open(format, sampleRate * channels * 2 / 2);
		l.start();
		line = l;
	}

	@Override
	public void write(byte[] pcm16le, int length) {
		SourceDataLine l = line;
		if (l != null) l.write(pcm16le, 0, length);
	}

	@Override
	public void close() {
		SourceDataLine l = line;
		line = null;
		if (l != null) {
			l.stop();
			l.flush();
			l.close();
		}
	}
}
