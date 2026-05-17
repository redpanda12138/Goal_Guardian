<template>
  <view class="page-coach">
    <CommonHeader title="Talkie" backgroundColor="#ffffff">
      <template v-slot:content>
        <text class="page-title">Coach</text>
      </template>
    </CommonHeader>
    <view class="content coach-page">
      <view class="chat-tab-box">
        <view :class="`chat-tab ${tabNum === '1' ? 'chat-tab-actice' : ''}`" @tap="tabChange('1')">Goals</view>
        <view :class="`chat-tab ${tabNum === '2' ? 'chat-tab-actice' : ''}`" @tap="tabChange('2')">Profile</view>
      </view>

      <scroll-view
        v-show="tabNum === '1'"
        scroll-y
        class="coach-scroll"
        :scroll-top="0"
      >
        <view class="review-strip">
          <text class="review-label">Next review</text>
          <text class="review-val">{{ nextReviewDisplay }}</text>
        </view>

        <view class="summary-card">
          <text class="summary-title">Latest summary</text>
          <view class="summary-body" :class="{ muted: summaryMuted }">
            <template v-if="summaryBlocks.length">
              <template v-for="(block, blockIndex) in summaryBlocks" :key="'summary-block-' + blockIndex">
                <text v-if="block.type === 'paragraph'" class="summary-paragraph">
                  <text
                    v-for="(run, runIndex) in block.runs"
                    :key="'summary-run-' + blockIndex + '-' + runIndex"
                    :class="{ 'summary-strong': run.type === 'bold' }"
                  >{{ run.text }}</text>
                </text>

                <view v-else class="summary-list">
                  <view
                    v-for="(item, itemIndex) in block.items"
                    :key="'summary-item-' + blockIndex + '-' + itemIndex"
                    class="summary-list-item"
                  >
                    <text class="summary-list-bullet">•</text>
                    <text class="summary-list-text">
                      <text
                        v-for="(run, runIndex) in item"
                        :key="'summary-item-run-' + blockIndex + '-' + itemIndex + '-' + runIndex"
                        :class="{ 'summary-strong': run.type === 'bold' }"
                      >{{ run.text }}</text>
                    </text>
                  </view>
                </view>
              </template>
            </template>
            <text v-else>{{ summaryDisplayText }}</text>
          </view>
        </view>

        <view class="goal-section">
          <text class="goal-section-heading">Goals</text>
          <view class="goal-list">
            <template v-if="goalListLoading">
              <view class="goal-card goal-card-placeholder">
                <text class="goal-placeholder-body">Loading goals...</text>
              </view>
            </template>
            <template v-else-if="goalsDisplayList.length">
              <view v-for="g in goalsDisplayList" :key="'g-' + g.index" class="goal-card">
                <view class="goal-row-top">
                  <text class="goal-label">{{ g.smart_label }}</text>
                  <text v-if="g.completed" class="goal-done">Done</text>
                </view>
                <text class="goal-text">{{ g.text }}</text>
                <view class="goal-actions">
                  <view class="goal-btn" @tap="onMarkComplete(g.index)">Mark complete</view>
                  <view class="goal-btn ghost" @tap="goChat">Discuss in chat</view>
                </view>
              </view>
            </template>
            <view v-else class="goal-card goal-card-placeholder">
              <text class="goal-placeholder-title">No goals listed yet</text>
              <text class="goal-placeholder-body">
                Talk with your health coach to add goals. They do not need to be in SMART format - any clear intention or habit you want to work on is fine.
              </text>
              <view class="goal-actions">
                <view class="goal-btn ghost full-width" @tap="goChat">Open chat to add goals</view>
              </view>
            </view>
          </view>
        </view>

        <CoachWeeklyReviewCard
          :review="dashboard?.weekly_review"
          :loading="dashboardLoading"
          :stale="dashboardStale"
          :last-updated-at="dashboardLastUpdatedAt"
        />

        <CoachOverallReviewCard
          :review="dashboard?.overall_review"
          :loading="dashboardLoading || overallReviewLoading"
          :active-window="overallReviewDisplayWindow"
          :stale="dashboardStale"
          :last-updated-at="dashboardLastUpdatedAt"
          @window-change="refreshOverallReview"
        />

        <view class="bottom-actions">
          <view class="btn-main" @tap="goChat">Continue Health Coach Chat</view>
        </view>
      </scroll-view>

      <scroll-view
        v-show="tabNum === '2'"
        scroll-y
        class="coach-scroll profile-scroll"
      >
        <view v-if="settingLoading" class="loading-container">
          <loading-round />
        </view>
        <view v-else-if="patientInfo" class="setting-container">
          <view class="info-section">
            <text class="info-label">Preferred Name:</text>
            <text class="info-value">{{ patientInfo.preferred_name || "Not set" }}</text>
          </view>
          <view class="info-section">
            <text class="info-label">Hobbies:</text>
            <view v-if="patientInfo.hobbies && patientInfo.hobbies.length > 0" class="info-list">
              <text v-for="(hobby, index) in patientInfo.hobbies" :key="index" class="info-tag">{{ hobby }}</text>
            </view>
            <text v-else class="info-empty">No entries yet</text>
          </view>
          <view class="info-section">
            <text class="info-label">Family:</text>
            <view v-if="patientInfo.family && patientInfo.family.length > 0" class="info-list">
              <text v-for="(item, index) in patientInfo.family" :key="index" class="info-tag">{{ item }}</text>
            </view>
            <text v-else class="info-empty">No entries yet</text>
          </view>
          <view class="info-section">
            <text class="info-label">Friends:</text>
            <view v-if="patientInfo.friends && patientInfo.friends.length > 0" class="info-list">
              <text v-for="(item, index) in patientInfo.friends" :key="index" class="info-tag">{{ item }}</text>
            </view>
            <text v-else class="info-empty">No entries yet</text>
          </view>
          <view class="info-section">
            <text class="info-label">Travel:</text>
            <view v-if="patientInfo.travel && patientInfo.travel.length > 0" class="info-list">
              <text v-for="(item, index) in patientInfo.travel" :key="index" class="info-tag">{{ item }}</text>
            </view>
            <text v-else class="info-empty">No entries yet</text>
          </view>
        </view>
        <view v-else class="empty-container">
          <text class="empty-text">No patient information available.</text>
        </view>
      </scroll-view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";

import LoadingRound from "@/components/LoadingRound.vue";
import CommonHeader from "@/components/CommonHeader.vue";
import masRequest from "@/api/mas";
import chatRequest from "@/api/chat";
import { formatNextAppointmentText } from "@/utils/masCoachReminder";
import CoachWeeklyReviewCard from "./components/CoachWeeklyReviewCard.vue";
import CoachOverallReviewCard from "./components/CoachOverallReviewCard.vue";
import summaryMarkdown from "./components/summaryMarkdown";
import {
  formatReviewTimestamp,
  type ReviewWindow,
  normalizeReviewWindow,
} from "./components/coachReviewFormatters";

function unwrapMasData(res: any): any {
  if (res == null) return null;
  if (typeof res !== "object") return res;
  if ("data" in res && res.data !== undefined) return res.data;
  return res;
}

function pickSummariesList(payload: any): any[] {
  const data = unwrapMasData(payload);
  if (!data) return [];
  if (Array.isArray(data)) return data;
  if (typeof data !== "object") return [];
  const list = data.summaries ?? data.list ?? data.items;
  return Array.isArray(list) ? list : [];
}

function hasDashboardGoals(dash: Record<string, any> | null | undefined): boolean {
  if (!dash || typeof dash !== "object") return false;
  return (
    (Array.isArray(dash.goals_detail) && dash.goals_detail.length > 0) ||
    (Array.isArray(dash.smart_goals) && dash.smart_goals.length > 0)
  );
}

function mergeDashboardGoals(
  dash: Record<string, any> | null,
  goalsPayload: any,
): Record<string, any> | null {
  const goalsApi = unwrapMasData(goalsPayload);
  const smartGoals = goalsApi?.smart_goals;
  if (!Array.isArray(smartGoals) || smartGoals.length === 0) return dash;

  if (!dash) {
    return { smart_goals: smartGoals, goals_detail: [] };
  }
  if (hasDashboardGoals(dash)) return dash;
  return { ...dash, smart_goals: smartGoals };
}

function createEmptyOverallReview(window: ReviewWindow) {
  return {
    window,
    kpi: {
      planned_total: 0,
      completed_total: 0,
      completion_rate: null,
    },
    completion_rate_trend: [],
    plan_vs_done_trend: [],
    cumulative_progress_trend: [],
  };
}

const dashboard = ref<Record<string, any> | null>(null);
const dashboardLoading = ref(false);
const overallReviewWindow = ref<ReviewWindow>("5");
const overallReviewPendingWindow = ref<ReviewWindow | "">("");
const overallReviewRequestId = ref(0);
const overallReviewLoading = ref(false);
const overallReviewDisplayWindow = computed<ReviewWindow>(
  () => overallReviewPendingWindow.value || overallReviewWindow.value
);
const dashboardStale = ref(false);
const dashboardLastUpdatedAt = ref("");
const patientInfo = ref<any>(null);
const settingLoading = ref(false);
const profileRequested = ref(false);
const summariesPayload = ref<any>(null);
const summaryLoading = ref(false);
const goalsLoading = ref(false);
const tabNum = ref<string>("1");

const goalsDetail = computed(() => {
  const value = dashboard.value?.goals_detail;
  return Array.isArray(value) ? value : [];
});

const goalsDisplayList = computed(() => {
  const detail = goalsDetail.value;
  if (detail.length) return detail;

  const raw = dashboard.value?.smart_goals;
  if (Array.isArray(raw) && raw.length) {
    return raw.map((text: any, index: number) => ({
      index,
      text: typeof text === "string" ? text : String(text),
      smart_label: "Goal",
      completed: false,
    }));
  }
  return [];
});

const goalListLoading = computed(() => dashboardLoading.value || goalsLoading.value);

const nextReviewDisplay = computed(() => {
  if (dashboardLoading.value) return "Loading...";
  const reviewTime = dashboard.value?.next_review_time;
  if (!reviewTime) return "Not scheduled yet";
  return formatNextAppointmentText(reviewTime) || String(reviewTime);
});

const summaryPlaceholder =
  "No summary yet. After a coaching session, a summary may appear here.";

const lastSummaryText = computed(() => {
  const raw = summariesPayload.value;
  if (!raw) return "";

  const list = pickSummariesList(raw);
  if (list.length > 0) {
    const scored = list.map((item: any, index: number) => {
      const timestamp =
        Date.parse(item?.created_at || item?.updated_at || item?.timestamp || item?.time || "") || 0;
      return { item, timestamp, index };
    });
    const hasAnyTimestamp = scored.some((entry) => entry.timestamp > 0);
    const latestItem = hasAnyTimestamp
      ? scored.reduce((left, right) => (right.timestamp >= left.timestamp ? right : left)).item
      : list[list.length - 1];

    if (typeof latestItem === "string") return latestItem;
    if (latestItem && typeof latestItem === "object") {
      const text = latestItem.summary ?? latestItem.text ?? latestItem.content ?? latestItem.body;
      if (typeof text === "string") return text;
    }
    try {
      return JSON.stringify(latestItem);
    } catch {
      return "";
    }
  }

  const data = unwrapMasData(raw);
  if (typeof data === "string") return data;
  if (data && typeof data === "object" && typeof data.summary === "string") {
    return data.summary;
  }
  return "";
});

const summaryDisplayText = computed(() => {
  if (summaryLoading.value && !lastSummaryText.value) {
    return "Loading summary...";
  }
  return lastSummaryText.value || summaryPlaceholder;
});

const summaryBlocks = computed(() => {
  if (!lastSummaryText.value) return [];
  return summaryMarkdown.parseSummaryMarkdown(lastSummaryText.value);
});

const summaryMuted = computed(() => !lastSummaryText.value);

onMounted(() => {
  uni.setNavigationBarTitle({ title: "Goal Guardian" });
});

onShow(() => {
  nextTick(() => {
    loadDashboard().finally(() => {
      setTimeout(() => {
        void loadSummaries();
      }, 0);
    });

    if (tabNum.value === "2") {
      void ensureProfileLoaded();
    }
  });
});

const loadGoalsFallback = () => {
  if (goalsLoading.value) return Promise.resolve();

  goalsLoading.value = true;
  return masRequest
    .getPatientGoals()
    .then((res: any) => {
      dashboard.value = mergeDashboardGoals(dashboard.value, res);
    })
    .catch(() => undefined)
    .finally(() => {
      goalsLoading.value = false;
    });
};

const loadDashboard = (window: ReviewWindow = overallReviewWindow.value) => {
  const normalizedWindow = normalizeReviewWindow(window);
  const previousDashboard = dashboard.value;
  dashboardLoading.value = true;

  return masRequest
    .getCoachDashboard(normalizedWindow)
    .then((res: any) => {
      const nextDashboard = unwrapMasData(res) as Record<string, any> | null;
      dashboard.value = nextDashboard;
      overallReviewWindow.value = normalizeReviewWindow(
        nextDashboard?.overall_review?.window ?? normalizedWindow
      );
      overallReviewPendingWindow.value = "";
      dashboardStale.value = false;
      dashboardLastUpdatedAt.value = formatReviewTimestamp(new Date());

      if (!hasDashboardGoals(nextDashboard)) {
        void loadGoalsFallback();
      }
    })
    .catch(() => {
      dashboard.value = previousDashboard;
      dashboardStale.value = !!previousDashboard;
    })
    .finally(() => {
      dashboardLoading.value = false;
    });
};

const refreshOverallReview = (window: ReviewWindow) => {
  const nextWindow = normalizeReviewWindow(window);
  const activeWindow = overallReviewPendingWindow.value || overallReviewWindow.value;
  if (nextWindow === activeWindow) {
    return Promise.resolve();
  }

  const requestId = overallReviewRequestId.value + 1;
  overallReviewRequestId.value = requestId;
  overallReviewPendingWindow.value = nextWindow;
  overallReviewLoading.value = true;

  return masRequest
    .getCoachDashboard(nextWindow)
    .then((res: any) => {
      if (requestId !== overallReviewRequestId.value) return;

      const nextDashboard = unwrapMasData(res) as Record<string, any> | null;
      const nextOverall = nextDashboard?.overall_review || createEmptyOverallReview(nextWindow);
      const resolvedWindow = normalizeReviewWindow(nextOverall?.window ?? nextWindow);
      dashboard.value = {
        ...(dashboard.value || nextDashboard || {}),
        overall_review: {
          ...nextOverall,
          window: resolvedWindow,
        },
      };
      overallReviewWindow.value = resolvedWindow;
      dashboardStale.value = false;
      dashboardLastUpdatedAt.value = formatReviewTimestamp(new Date());
    })
    .catch(() => {
      if (requestId !== overallReviewRequestId.value) return;
      dashboardStale.value = !!dashboard.value;
    })
    .finally(() => {
      if (requestId !== overallReviewRequestId.value) return;
      overallReviewLoading.value = false;
      overallReviewPendingWindow.value = "";
    });
};

const loadSummaries = () => {
  if (summaryLoading.value) return Promise.resolve();

  summaryLoading.value = true;
  return masRequest
    .getSessionSummaries()
    .then((res: any) => {
      summariesPayload.value = res?.data !== undefined ? res.data : res;
    })
    .catch(() => {
      summariesPayload.value = null;
    })
    .finally(() => {
      summaryLoading.value = false;
    });
};

const getSetting = () => {
  profileRequested.value = true;
  settingLoading.value = true;
  return masRequest
    .getPatientInfo()
    .then((res: any) => {
      const raw = unwrapMasData(res);
      patientInfo.value = raw && typeof raw === "object" && !Array.isArray(raw) ? raw : null;
    })
    .catch(() => {
      patientInfo.value = null;
    })
    .finally(() => {
      settingLoading.value = false;
    });
};

const ensureProfileLoaded = () => {
  if (profileRequested.value || settingLoading.value) {
    return Promise.resolve();
  }
  return getSetting();
};

const tabChange = (type: "1" | "2") => {
  tabNum.value = type;
  if (type === "2") {
    void ensureProfileLoaded();
  }
};

const onMarkComplete = (goalIndex: number) => {
  const activeWindow = overallReviewDisplayWindow.value;
  masRequest
    .postCoachStateEvent({ event_type: "goal_completed", goal_index: goalIndex })
    .then((res: any) => {
      const payload = unwrapMasData(res);
      const nextDashboard = payload?.dashboard || res?.data?.dashboard;
      if (nextDashboard) {
        dashboard.value = nextDashboard;
        overallReviewWindow.value = normalizeReviewWindow(
          nextDashboard?.overall_review?.window ?? "5"
        );
        overallReviewPendingWindow.value = "";
        if (!hasDashboardGoals(nextDashboard)) {
          void loadGoalsFallback();
        }
      }
      dashboardStale.value = false;
      dashboardLastUpdatedAt.value = formatReviewTimestamp(new Date());
      const followUp = activeWindow !== "5" ? refreshOverallReview(activeWindow) : Promise.resolve();
      return Promise.resolve(followUp).finally(() => {
        uni.showToast({ title: "Updated", icon: "success" });
      });
    })
    .catch(() => {
      uni.showToast({ title: "Failed", icon: "none" });
    });
};

const goChat = () => {
  chatRequest
    .sessionMasGetOrCreate()
    .then((res: any) => {
      const id = res?.data?.id;
      if (id) {
        uni.navigateTo({ url: `/pages/chat/index?sessionId=${id}` });
        return;
      }
      uni.showToast({ title: "No session", icon: "none" });
    })
    .catch(() => {
      uni.showToast({ title: "Failed", icon: "none" });
    });
};
</script>

<style lang="scss">
@import "@/less/coach-purple.scss";

.page-coach {
  min-height: 100vh;
  background: $coach-purple-surface;
}

.page-title {
  display: inline-block;
  font-size: 38rpx;
  font-weight: 450;
  position: relative;
  top: 8rpx;
}

.content {
  display: flex;
  flex-direction: column;
}

.coach-page {
  position: relative;
  min-height: calc(100vh - 120rpx);
}

.chat-tab-box {
  display: flex;
  padding: 32rpx;
  align-items: center;

  .chat-tab {
    margin-right: 44rpx;
    font-size: 36rpx;
    position: relative;
    display: flex;
    justify-content: center;
    transition: 0.1s all linear;
    height: 50rpx;
    line-height: 50rpx;
    color: $coach-text-muted;
  }

  .chat-tab-actice {
    font-size: 42rpx;
    font-weight: 600;
    color: $coach-purple-800;
  }

  .chat-tab-actice::after {
    position: absolute;
    content: "";
    background: $coach-purple-500;
    width: 40rpx;
    height: 10rpx;
    border-radius: 5rpx;
    bottom: -20rpx;
  }
}

.coach-scroll {
  height: calc(100vh - 280rpx);
  padding: 0 24rpx 48rpx;
  box-sizing: border-box;
}

.profile-scroll {
  padding-top: 8rpx;
}

.review-strip {
  background: $coach-purple-50;
  border-radius: 16rpx;
  padding: 20rpx 24rpx;
  margin-bottom: 20rpx;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  border: 1rpx solid rgba(124, 92, 191, 0.18);
}

.review-label {
  font-size: 24rpx;
  color: $coach-text-muted;
}

.review-val {
  font-size: 28rpx;
  font-weight: 600;
  color: $coach-purple-800;
}

.summary-card {
  background: rgba(255, 255, 255, 0.92);
  border: 1rpx solid rgba(124, 92, 191, 0.2);
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 4rpx 20rpx rgba(93, 61, 158, 0.06);
}

.summary-title {
  font-size: 26rpx;
  font-weight: 600;
  color: $coach-accent;
  display: block;
  margin-bottom: 12rpx;
}

.summary-body {
  font-size: 26rpx;
  color: $coach-text-body;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;

  &.muted {
    color: $coach-text-muted;
    font-style: italic;
  }
}

.summary-paragraph {
  display: block;
  margin-bottom: 12rpx;
}

.summary-paragraph:last-child {
  margin-bottom: 0;
}

.summary-list {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
  margin: 4rpx 0 12rpx;
}

.summary-list:last-child {
  margin-bottom: 0;
}

.summary-list-item {
  display: flex;
  align-items: flex-start;
  gap: 10rpx;
}

.summary-list-bullet {
  flex: none;
  line-height: 1.5;
  color: $coach-purple-700;
}

.summary-list-text {
  flex: 1;
  line-height: 1.5;
}

.summary-strong {
  font-weight: 700;
  color: $coach-text-strong;
}

.info-empty {
  font-size: 26rpx;
  color: $coach-text-muted;
}

.goal-section {
  width: 100%;
  margin-bottom: 8rpx;
}

.goal-section-heading {
  font-size: 30rpx;
  font-weight: 600;
  color: $coach-purple-800;
  margin-bottom: 16rpx;
  padding-left: 4rpx;
}

.goal-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.goal-card-placeholder {
  border-style: dashed;
  border-color: rgba(124, 92, 191, 0.35);
}

.goal-placeholder-title {
  display: block;
  font-size: 28rpx;
  font-weight: 600;
  color: $coach-purple-800;
  margin-bottom: 12rpx;
}

.goal-placeholder-body {
  display: block;
  font-size: 26rpx;
  color: $coach-text-body;
  line-height: 1.5;
}

.goal-btn.full-width {
  flex: none;
  width: 72%;
  min-width: 280rpx;
  max-width: 420rpx;
  margin: 0 auto;
}

.goal-card {
  background: $coach-purple-surface;
  border-radius: 20rpx;
  padding: 24rpx;
  border: 1rpx solid rgba(124, 92, 191, 0.2);
}

.goal-row-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12rpx;
}

.goal-label {
  font-size: 22rpx;
  color: $coach-purple-700;
  background: rgba(108, 92, 231, 0.14);
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
}

.goal-done {
  font-size: 24rpx;
  color: #6b4c9a;
}

.goal-text {
  font-size: 28rpx;
  color: $coach-text-strong;
  line-height: 1.45;
}

.goal-actions {
  display: flex;
  gap: 16rpx;
  margin-top: 20rpx;
}

.goal-btn {
  flex: 1;
  text-align: center;
  padding: 16rpx;
  border-radius: 12rpx;
  font-size: 24rpx;
  background: $coach-purple-600;
  color: #fff;
  box-shadow: 0 4rpx 12rpx rgba(108, 92, 231, 0.22);
}

.goal-btn.ghost {
  background: rgba(255, 255, 255, 0.95);
  color: $coach-purple-700;
  border: 1rpx solid rgba(124, 92, 191, 0.45);
  box-shadow: none;
}

/* 与目标卡同宽：不拉满屏外，仅占 scroll 内容区 */
.bottom-actions {
  margin-top: 32rpx;
  margin-bottom: 48rpx;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  display: flex;
  justify-content: center;
}

.btn-main {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  text-align: center;
  padding: 24rpx 28rpx;
  border-radius: 16rpx;
  background: $coach-purple-600;
  color: #fff;
  font-size: 30rpx;
  font-weight: 500;
  box-shadow: 0 10rpx 28rpx rgba(92, 61, 158, 0.28);
}

.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 40rpx;
}

.empty-container {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 60rpx 32rpx;
}

.empty-text {
  font-size: 28rpx;
  color: $coach-text-muted;
  text-align: center;
}

.setting-container {
  padding: 24rpx;
}

.info-section {
  margin-bottom: 28rpx;
}

.info-label {
  font-size: 26rpx;
  color: #888;
  display: block;
  margin-bottom: 8rpx;
}

.info-value {
  font-size: 30rpx;
  color: #333;
}

.info-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}

.info-tag {
  background: $coach-purple-100;
  padding: 8rpx 16rpx;
  border-radius: 8rpx;
  font-size: 26rpx;
  color: $coach-purple-800;
  border: 1rpx solid rgba(124, 92, 191, 0.12);
}
</style>


