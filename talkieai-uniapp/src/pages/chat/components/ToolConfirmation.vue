<template>
  <view
    class="tool-confirmation"
    role="group"
    :aria-label="copy.title"
    aria-live="polite"
  >
    <template v-if="['pending', 'submitting', 'cancelling'].includes(state.status)">
      <text class="tool-confirmation__eyebrow">Confirmation required</text>
      <text class="tool-confirmation__title">{{ copy.title }}</text>
      <text class="tool-confirmation__detail">{{ copy.detail }}</text>
      <view class="tool-confirmation__actions">
        <button
          class="tool-confirmation__button tool-confirmation__button--secondary"
          :disabled="state.status !== 'pending'"
          aria-label="Cancel this proposed action"
          @tap="$emit('cancel')"
        >
          {{ state.status === "cancelling" ? "Cancelling…" : "Cancel" }}
        </button>
        <button
          class="tool-confirmation__button tool-confirmation__button--primary"
          :disabled="state.status !== 'pending'"
          :aria-busy="state.status === 'submitting'"
          :aria-label="copy.confirmLabel"
          @tap="$emit('confirm')"
        >
          {{ state.status === "submitting" ? "Working…" : copy.confirmLabel }}
        </button>
      </view>
    </template>

    <view v-else-if="state.status === 'completed'" class="tool-confirmation__status" role="status">
      <text class="tool-confirmation__status-mark" aria-hidden="true">✓</text>
      <text>Action confirmed and completed.</text>
    </view>
    <view v-else-if="state.status === 'cancelled'" class="tool-confirmation__status" role="status">
      <text>No change was made.</text>
    </view>
    <view v-else-if="state.status === 'failed'" class="tool-confirmation__status tool-confirmation__status--error" role="alert">
      <text>{{ state.error }}</text>
    </view>
    <view v-else class="tool-confirmation__status tool-confirmation__status--error" role="alert">
      <text>{{ state.error }}</text>
      <button
        class="tool-confirmation__button tool-confirmation__button--secondary tool-confirmation__refresh"
        aria-label="Refresh chat to verify the action result"
        @tap="$emit('refresh')"
      >
        Refresh chat
      </button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { ToolConfirmationState } from "@/models/models";
import { toolConfirmationCopy } from "@/pages/chat/toolConfirmationState.mjs";

const props = defineProps<{ state: ToolConfirmationState }>();
defineEmits<{
  (event: "confirm"): void;
  (event: "cancel"): void;
  (event: "refresh"): void;
}>();

const copy = computed(() => toolConfirmationCopy(props.state.request));
</script>

<style lang="less" scoped>
@import url("@/less/coach-purple.less");

.tool-confirmation {
  margin-top: 24rpx;
  padding: 24rpx;
  border: 1rpx solid rgba(124, 92, 191, 0.24);
  border-radius: 12rpx;
  background: @coach-purple-50;
  color: @coach-purple-900;
}

.tool-confirmation__eyebrow,
.tool-confirmation__title,
.tool-confirmation__detail {
  display: block;
}

.tool-confirmation__eyebrow {
  margin-bottom: 8rpx;
  color: @coach-purple-700;
  font-size: 22rpx;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.tool-confirmation__title {
  font-size: 30rpx;
  font-weight: 600;
  line-height: 1.4;
}

.tool-confirmation__detail {
  margin-top: 8rpx;
  color: #4a3d5f;
  font-size: 26rpx;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.tool-confirmation__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
  margin-top: 24rpx;
}

.tool-confirmation__button {
  flex: 1 1 220rpx;
  min-height: 88rpx;
  margin: 0;
  padding: 16rpx 24rpx;
  border-radius: 10rpx;
  font-size: 28rpx;
  font-weight: 600;
  line-height: 1.4;

  &::after {
    border: 0;
  }

  &[disabled] {
    opacity: 0.62;
  }
}

.tool-confirmation__button--primary {
  background: @coach-purple-700;
  color: #fff;
}

.tool-confirmation__button--secondary {
  border: 1rpx solid @coach-purple-300;
  background: #fff;
  color: @coach-purple-900;
}

.tool-confirmation__status {
  display: flex;
  align-items: center;
  gap: 12rpx;
  font-size: 26rpx;
  line-height: 1.5;
}

.tool-confirmation__status-mark {
  color: #16785b;
  font-size: 32rpx;
  font-weight: 700;
}

.tool-confirmation__status--error {
  align-items: flex-start;
  flex-direction: column;
  color: #7a2632;
}

.tool-confirmation__refresh {
  flex: none;
  margin-top: 16rpx;
}
</style>
