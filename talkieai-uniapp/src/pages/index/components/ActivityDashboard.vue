<template>
  <view class="activity-dashboard">
    <CoachDashboardCards
      :dashboard="dashboard"
      :loading="loading"
      @mark-complete="onMarkComplete"
      @modify="onModify"
      @next-tap="onNextTap"
    />
    <view class="bottom-section">
      <view class="deco-shapes">
        <view class="deco-dot deco-dot-1" />
        <view class="deco-dot deco-dot-2" />
      </view>
      <view class="btn btn-add" @tap="onAddActivity">
        <text class="btn-add-text">Add Activity +</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import CoachDashboardCards from "@/components/CoachDashboardCards.vue";
import masRequest from "@/api/mas";
import chatRequest from "@/api/chat";

const props = defineProps<{
  dashboard: Record<string, any> | null;
  loading?: boolean;
}>();

const emit = defineEmits<{
  (e: "dashboard-updated", payload: Record<string, any>): void;
}>();

const onMarkComplete = (goalIndex: number) => {
  masRequest
    .postCoachStateEvent({ event_type: "goal_completed", goal_index: goalIndex })
    .then((res: any) => {
      const dash = res?.data?.dashboard;
      if (dash) {
        emit("dashboard-updated", dash);
      }
      uni.showToast({ title: "Marked complete", icon: "success" });
    })
    .catch(() => {
      uni.showToast({ title: "Failed to update", icon: "none" });
    });
};

const onModify = () => {
  uni.navigateTo({ url: "/pages/my/schedule" });
};

const onNextTap = () => {
  uni.showToast({ title: "See Next Workout on Coach tab", icon: "none" });
};

const onAddActivity = () => {
  chatRequest.sessionMasGetOrCreate().then((res: any) => {
    const id = res?.data?.id;
    if (id) {
      uni.navigateTo({ url: `/pages/chat/index?sessionId=${id}` });
      return;
    }
    uni.showToast({ title: "No session", icon: "none" });
  });
};
</script>

<style lang="scss" scoped>
@import "@/less/coach-purple.scss";

.activity-dashboard {
  width: 100%;
  padding: 0 0 40rpx;
}

.bottom-section {
  position: relative;
  padding-top: 10rpx;
}

.deco-shapes {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  height: 60rpx;
  pointer-events: none;
}

.deco-dot {
  position: absolute;
  border-radius: 50%;
  background: $coach-purple-200;
}
.deco-dot-1 {
  left: 24rpx;
  top: 12rpx;
  width: 20rpx;
  height: 20rpx;
  background: $coach-purple-400;
}
.deco-dot-2 {
  left: 56rpx;
  top: 28rpx;
  width: 12rpx;
  height: 12rpx;
  background: $coach-accent-soft;
  opacity: 0.95;
}

.btn-add {
  width: 100%;
  height: 88rpx;
  background: $coach-purple-600;
  color: #fff;
  border-radius: 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8rpx 24rpx rgba(108, 92, 231, 0.3);
}

.btn-add-text {
  font-size: 32rpx;
  font-weight: 500;
  letter-spacing: 0.5rpx;
}
</style>
