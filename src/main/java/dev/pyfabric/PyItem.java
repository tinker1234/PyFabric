package dev.pyfabric;

import java.util.function.Consumer;

import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.TooltipFlag;
import net.minecraft.world.item.component.TooltipDisplay;
import net.minecraft.world.item.context.UseOnContext;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.state.BlockState;
import org.graalvm.polyglot.Value;

/** An Item whose behaviour is defined by Python hooks. Missing hooks fall back to vanilla Item behaviour. */
public class PyItem extends Item {
	public final Hooks hooks;

	public PyItem(Properties properties, String id) {
		super(properties);
		this.hooks = new Hooks("item " + id);
	}

	@Override
	public InteractionResult use(Level level, Player player, InteractionHand hand) {
		Object r = hooks.call("use", InteractionResult.class, level, player, hand);
		return r instanceof InteractionResult ir ? ir : super.use(level, player, hand);
	}

	@Override
	public InteractionResult useOn(UseOnContext context) {
		Object r = hooks.call("use_on_block", InteractionResult.class, context);
		return r instanceof InteractionResult ir ? ir : super.useOn(context);
	}

	@Override
	public InteractionResult interactLivingEntity(ItemStack stack, Player player, LivingEntity target, InteractionHand hand) {
		Object r = hooks.call("use_on_entity", InteractionResult.class, stack, player, target, hand);
		return r instanceof InteractionResult ir ? ir : super.interactLivingEntity(stack, player, target, hand);
	}

	@Override
	public void hurtEnemy(ItemStack stack, LivingEntity target, LivingEntity attacker) {
		hooks.call("hit_entity", void.class, stack, target, attacker);
		super.hurtEnemy(stack, target, attacker);
	}

	@Override
	public boolean mineBlock(ItemStack stack, Level level, BlockState state, BlockPos pos, LivingEntity miner) {
		hooks.call("mine_block", void.class, stack, level, state, pos, miner);
		return super.mineBlock(stack, level, state, pos, miner);
	}

	@Override
	public void inventoryTick(ItemStack stack, ServerLevel level, Entity entity, EquipmentSlot slot) {
		hooks.call("inventory_tick", void.class, stack, level, entity, slot);
		super.inventoryTick(stack, level, entity, slot);
	}

	@Override
	public ItemStack finishUsingItem(ItemStack stack, Level level, LivingEntity entity) {
		ItemStack result = super.finishUsingItem(stack, level, entity);
		hooks.call("finish_using", void.class, stack, level, entity);
		return result;
	}

	@Override
	public void onCraftedBy(ItemStack stack, Player player) {
		hooks.call("crafted", void.class, stack, player);
		super.onCraftedBy(stack, player);
	}

	@Override
	public boolean isFoil(ItemStack stack) {
		Object r = hooks.call("glint", boolean.class, stack);
		return r instanceof Boolean b ? b : super.isFoil(stack);
	}

	@Override
	@SuppressWarnings("deprecation")
	public void appendHoverText(ItemStack stack, TooltipContext context, TooltipDisplay display,
								Consumer<Component> builder, TooltipFlag flag) {
		super.appendHoverText(stack, context, display, builder, flag);
		Value lines = hooks.callRaw("tooltip", stack);
		if (lines == null || lines.isNull()) return;
		if (lines.isString()) {
			builder.accept(Component.literal(lines.asString()).withStyle(ChatFormatting.GRAY));
		} else if (lines.hasArrayElements()) {
			for (long i = 0; i < lines.getArraySize(); i++) {
				Value line = lines.getArrayElement(i);
				if (line.isHostObject() && line.asHostObject() instanceof Component c) builder.accept(c);
				else builder.accept(Component.literal(line.isString() ? line.asString() : line.toString()).withStyle(ChatFormatting.GRAY));
			}
		} else if (lines.isHostObject() && lines.asHostObject() instanceof Component c) {
			builder.accept(c);
		}
	}
}
