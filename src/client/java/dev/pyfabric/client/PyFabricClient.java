package dev.pyfabric.client;

import dev.pyfabric.PythonHost;
import dev.pyfabric.client.radio.RadioClient;
import dev.pyfabric.client.radio.RadioCommand;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.command.v2.ClientCommandRegistrationCallback;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientLifecycleEvents;

/** Runs each Python mod's optional client.py (key bindings, HUD, rendering, client events) and sets up /radio. */
public class PyFabricClient implements ClientModInitializer {
	@Override
	public void onInitializeClient() {
		ClientCommandRegistrationCallback.EVENT.register((dispatcher, ctx) -> RadioCommand.register(dispatcher));
		ClientLifecycleEvents.CLIENT_STOPPING.register(client -> RadioClient.stop());
		PythonHost.get().call("load_client");
	}
}
