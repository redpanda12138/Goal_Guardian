<template>
  <view class="page-home">
    <CommonHeader backgroundColor="#ffffff">
      <template v-slot:content>
        <text class="page-title">Goal Guardian</text>
      </template>
    </CommonHeader>
    <view class="content">
      <!-- 自由聊天 -->
      <view class="index-page-card">
        <view class="index-header-box">
          <image src="/static/default-account-avatar.png" class="index-header-img" />
        </view>
        <view class="intro-box">
          <view class="top-box">
            <view class="index-name-wrap">
              <view class="index-name">
                <text class="index-name-text">Multi-Agent System (MAS)</text>
              </view>
            </view>
            <view class="right-column">
              <view @tap="goSchedule" class="appointment-block">
                <view class="appointment-row">
                  <uni-icons class="appointment-icon" type="calendar" size="14" color="#E8E8E8" />
                  <view class="appointment-text-col">
                    <text class="appointment-label">Next appointment:</text>
                    <text class="appointment-date">{{ nextAppointmentText }}</text>
                  </view>
                </view>
              </view>
              <view class="intro-bottom-box">
                <view @tap="goChat" class="index-btn">Chat With Coach</view>
              </view>
            </view>
          </view>
        </view>
      </view>

      <ActivityDashboard
        class="topic-component"
        :dashboard="coachDashboard"
        :loading="dashboardLoading"
        @dashboard-updated="onCoachDashboardUpdated"
      />
    </view>
  </view>
</template>

<script setup lang="ts">
import CommonHeader from "@/components/CommonHeader.vue";
import chatRequest from "@/api/chat";
import masRequest from "@/api/mas";
import ActivityDashboard from "./components/ActivityDashboard.vue";
import {
  unwrapNextReviewPayload,
  formatNextAppointmentText,
} from "@/utils/masCoachReminder";
import { onShow } from "@dcloudio/uni-app";
import { ref } from "vue";

const loading = ref(false);
const nextAppointmentText = ref("Not scheduled");
const coachDashboard = ref<Record<string, any> | null>(null);
const dashboardLoading = ref(false);

onShow(() => {
  initData();
  loadCoachDashboard();
});

const loadCoachDashboard = () => {
  dashboardLoading.value = true;
  masRequest
    .getCoachDashboard()
    .then((res: any) => {
      coachDashboard.value = res?.data ?? null;
    })
    .catch(() => {
      coachDashboard.value = null;
    })
    .finally(() => {
      dashboardLoading.value = false;
    });
};

const onCoachDashboardUpdated = (payload: Record<string, any>) => {
  coachDashboard.value = payload;
};

const initData = () => {
  loading.value = true;
  masRequest
    .getNextReviewTime()
    .then((res: any) => {
      const payload = unwrapNextReviewPayload(res);
      const nextIso = payload?.next_review_time;
      if (!nextIso) {
        nextAppointmentText.value = getDefaultNextAppointmentText();
        return;
      }

      const formatted = formatNextAppointmentText(nextIso);
      if (!formatted) {
        nextAppointmentText.value = getDefaultNextAppointmentText();
        return;
      }

      nextAppointmentText.value = formatted;
    })
    .catch(() => {
      nextAppointmentText.value = getDefaultNextAppointmentText();
    })
    .finally(() => {
      loading.value = false;
    });
};

/**
 * OA 默认逻辑：如果没有用户指定时间，则为“当前时间 + 7 天，09:00”
 */
const getDefaultNextAppointmentText = () => {
  const now = new Date();
  const target = new Date(now);
  target.setDate(target.getDate() + 7);
  target.setHours(9, 0, 0, 0);

  return target.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const goSchedule = () => {
  uni.navigateTo({
    url: "/pages/my/schedule",
  });
};

const goChat = () => {
  handleMasChat();
};
/** Home 与 Coach 共用同一 MAS 会话：get-or-create 后进入聊天 */
const handleMasChat = () => {
  chatRequest.sessionMasGetOrCreate().then((res: any) => {
    const id = res?.data?.id;
    if (id) {
      uni.navigateTo({
        url: `/pages/chat/index?sessionId=${id}`,
      });
      return;
    }
    uni.showToast({
      title: "Could not open coach chat",
      icon: "none",
    });
  }).catch((e) => {
    console.error("Failed to list MAS sessions:", e);
    const errorMsg = e?.detail || e?.message || "Unknown error";
    uni.showToast({
      title: `Failed to open chat: ${errorMsg}`,
      icon: "none",
      duration: 3000,
    });
  });
};
</script>
<style scoped lang="less">
@import url('@/less/global.less');
@import url('@/less/coach-purple.less');

.page-home {
  min-height: 100vh;
  background: @coach-purple-surface;
}

.page-title {
  display: inline-block;
  font-size: 38rpx;
  font-weight: 450;
  position: relative;
  top: 8rpx;
}


.content {
  padding-top: 10rpx;
  margin: 0 36rpx;
  display: flex;
  flex-direction: column;
  align-items: center;

  .index-page-card {
    margin: 0 36rpx;
    width: 100%;
    min-height: 200rpx;
    background: @coach-purple-500;
    box-shadow: 0 12rpx 36rpx rgba(92, 61, 158, 0.28);
    border-radius: 30rpx;
    padding: 24rpx 32rpx;
    display: flex;
    /* 头像、MAS 标题、右侧预约区：三块在卡片纵向上整体居中对齐 */
    align-items: center;

    .index-header-box {
      width: 108rpx;
      flex-shrink: 0;
      display: flex;
      align-items: center;
      justify-content: center;

      .index-header-img {
        width: 108rpx;
        height: 108rpx;
        border-radius: 54rpx;
        background: rgba(255, 255, 255, 0.25);
        border: 2rpx solid rgba(255, 255, 255, 0.45);
      }
    }

    .intro-box {
      flex: 1;
      min-width: 0;
      margin-left: 24rpx;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: stretch;

      .top-box {
        display: flex;
        width: 100%;
        justify-content: space-between;
        /* MAS 与右侧预约列互相对齐纵向中线 */
        align-items: center;
        gap: 16rpx;

        .index-name-wrap {
          flex: 1;
          min-width: 0;
          display: flex;
          align-items: center;
        }

        .index-name {
          color: #fff;
          width: 100%;
          overflow: hidden;
          text-overflow: ellipsis;

          .index-name-text {
            font-size: 26rpx;
            font-weight: 400;
            color: #FFFFFF;
            line-height: 30rpx;
            
          }
        }

        .right-column {
          flex-shrink: 0;
          width: 400rpx;
          max-width: 60%;
          display: flex;
          flex-direction: column;
          align-items: stretch;
          gap: 12rpx;
        }

        .appointment-block {
          width: 100%;
        }

        .appointment-row {
          display: flex;
          align-items: flex-start;
          gap: 8rpx;
        }

        .appointment-icon {
          flex-shrink: 0;
          margin-top: 2rpx;
        }

        .appointment-text-col {
          flex: 1;
          min-width: 0;
          display: flex;
          flex-direction: column;
          align-items: flex-start;
        }

        .appointment-label {
          color: #E8E8E8;
          font-size: 20rpx;
          line-height: 26rpx;
        }

        .appointment-date {
          color: #ffffff;
          font-size: 22rpx;
          line-height: 28rpx;
          font-weight: 500;
          margin-top: 2rpx;
        }

        .intro-bottom-box {
          width: 100%;
          margin-right: 0;
          background: #ffffff;
          border-radius: 24rpx;
          height: 56rpx;
          display: flex;
          justify-content: center;
          align-items: center;
          border: none;

          .index-btn {
            font-size: 24rpx;
            font-weight: 500;
            color: @coach-purple-900;
          }
        }
      }
    }
  }

  .topic-component {
    width: 100%;
    margin-top: 40rpx;
  }
}
</style>
