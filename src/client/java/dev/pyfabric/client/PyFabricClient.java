package dev.pyfabric.client;

import dev.pyfabric.PythonHost;
import net.fabricmc.api.ClientModInitializer;

/** Runs each Python mod's optional client.py (key bindings, HUD, rendering, client events). */
public class PyFabricClient implements ClientModInitializer {
	@Override
	public void onInitializeClient() {
		PythonHost.get().call("load_client");
	}
}
