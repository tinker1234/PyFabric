package dev.pyfabric;

import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.loader.api.FabricLoader;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class PyFabric implements ModInitializer {
	public static final String MOD_ID = "pyfabric";
	public static final Logger LOGGER = LoggerFactory.getLogger("PyFabric");

	@Override
	public void onInitialize() {
		ServerLifecycleEvents.SERVER_STARTING.register(Bridge::setServer);
		ServerLifecycleEvents.SERVER_STOPPED.register(s -> Bridge.setServer(null));
		CommandRegistrationCallback.EVENT.register((dispatcher, ctx, selection) -> PyFabricCommand.register(dispatcher));

		long start = System.currentTimeMillis();
		PythonHost host;
		try {
			host = PythonHost.start(FabricLoader.getInstance().getGameDir());
		} catch (Exception e) {
			throw new RuntimeException("PyFabric could not start the Python runtime", e);
		}
		LOGGER.info("Python runtime ready in {} ms; loading Python mods from {}", System.currentTimeMillis() - start, host.modsDir());
		host.call("load_main");
		LOGGER.info("PyFabric initialised in {} ms", System.currentTimeMillis() - start);
	}
}
