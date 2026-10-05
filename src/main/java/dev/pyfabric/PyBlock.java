package dev.pyfabric;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.RandomSource;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.InsideBlockEffectApplier;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.entity.projectile.Projectile;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.Explosion;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.redstone.Orientation;
import net.minecraft.world.phys.BlockHitResult;

/** A Block whose behaviour is defined by Python hooks. Missing hooks fall back to vanilla Block behaviour. */
public class PyBlock extends Block {
	public final Hooks hooks;

	public PyBlock(Properties properties, String id) {
		super(properties);
		this.hooks = new Hooks("block " + id);
	}

	@Override
	protected InteractionResult useWithoutItem(BlockState state, Level level, BlockPos pos, Player player, BlockHitResult hit) {
		Object r = hooks.call("use", InteractionResult.class, state, level, pos, player, hit);
		return r instanceof InteractionResult ir ? ir : super.useWithoutItem(state, level, pos, player, hit);
	}

	@Override
	protected InteractionResult useItemOn(ItemStack stack, BlockState state, Level level, BlockPos pos, Player player,
										  InteractionHand hand, BlockHitResult hit) {
		Object r = hooks.call("use_with_item", InteractionResult.class, stack, state, level, pos, player, hand, hit);
		return r instanceof InteractionResult ir ? ir : super.useItemOn(stack, state, level, pos, player, hand, hit);
	}

	@Override
	protected void attack(BlockState state, Level level, BlockPos pos, Player player) {
		hooks.call("punched", void.class, state, level, pos, player);
		super.attack(state, level, pos, player);
	}

	@Override
	public void stepOn(Level level, BlockPos pos, BlockState state, Entity entity) {
		hooks.call("stepped_on", void.class, level, pos, state, entity);
		super.stepOn(level, pos, state, entity);
	}

	@Override
	public void fallOn(Level level, BlockState state, BlockPos pos, Entity entity, double fallDistance) {
		Object r = hooks.call("fallen_on", boolean.class, level, state, pos, entity, fallDistance);
		if (Boolean.TRUE.equals(r)) return; // hook returned True: cancel vanilla fall damage
		super.fallOn(level, state, pos, entity, fallDistance);
	}

	@Override
	protected void entityInside(BlockState state, Level level, BlockPos pos, Entity entity,
								InsideBlockEffectApplier effects, boolean intersects) {
		hooks.call("entity_inside", void.class, state, level, pos, entity);
		super.entityInside(state, level, pos, entity, effects, intersects);
	}

	@Override
	public void setPlacedBy(Level level, BlockPos pos, BlockState state, LivingEntity placer, ItemStack stack) {
		super.setPlacedBy(level, pos, state, placer, stack);
		hooks.call("placed", void.class, level, pos, state, placer, stack);
	}

	@Override
	public BlockState playerWillDestroy(Level level, BlockPos pos, BlockState state, Player player) {
		hooks.call("broken", void.class, level, pos, state, player);
		return super.playerWillDestroy(level, pos, state, player);
	}

	@Override
	public void wasExploded(ServerLevel level, BlockPos pos, Explosion explosion) {
		hooks.call("exploded", void.class, level, pos, explosion);
		super.wasExploded(level, pos, explosion);
	}

	@Override
	protected boolean isRandomlyTicking(BlockState state) {
		return hooks.has("random_tick") || super.isRandomlyTicking(state);
	}

	@Override
	protected void randomTick(BlockState state, ServerLevel level, BlockPos pos, RandomSource random) {
		hooks.call("random_tick", void.class, state, level, pos, random);
		super.randomTick(state, level, pos, random);
	}

	@Override
	protected void tick(BlockState state, ServerLevel level, BlockPos pos, RandomSource random) {
		hooks.call("scheduled_tick", void.class, state, level, pos, random);
		super.tick(state, level, pos, random);
	}

	@Override
	public void animateTick(BlockState state, Level level, BlockPos pos, RandomSource random) {
		hooks.call("animate_tick", void.class, state, level, pos, random);
		super.animateTick(state, level, pos, random);
	}

	@Override
	protected void neighborChanged(BlockState state, Level level, BlockPos pos, Block neighbor, Orientation orientation, boolean moved) {
		hooks.call("neighbor_changed", void.class, state, level, pos, neighbor);
		super.neighborChanged(state, level, pos, neighbor, orientation, moved);
	}

	@Override
	protected void onProjectileHit(Level level, BlockState state, BlockHitResult hit, Projectile projectile) {
		hooks.call("projectile_hit", void.class, level, state, hit, projectile);
		super.onProjectileHit(level, state, hit, projectile);
	}

	@Override
	protected boolean isSignalSource(BlockState state) {
		return hooks.has("redstone_power") || super.isSignalSource(state);
	}

	@Override
	protected int getSignal(BlockState state, BlockGetter level, BlockPos pos, Direction direction) {
		Object r = hooks.call("redstone_power", int.class, state, level, pos, direction);
		return r instanceof Integer i ? Math.clamp(i, 0, 15) : super.getSignal(state, level, pos, direction);
	}
}
