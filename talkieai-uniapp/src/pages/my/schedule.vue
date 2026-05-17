<template>
    <view class="schedule-page">
        <CommonHeader :leftIcon="true" :back-fn="handleBack">
            <template v-slot:content>
                <text class="schedule-header-title">Schedule Coaching</text>
            </template>
        </CommonHeader>
        <view class="schedule-content">
            <view class="schedule-card">
                <text class="schedule-title">Select next session time</text>
                <text class="schedule-desc">The server triggers your session after the scheduled time (checked every 30 minutes). While the app is open, you may be taken to Chat when the session starts. You can always open Chat With Coach from Home. Times use your device clock and are sent to the server in UTC. If you leave date/time empty, the default is 7 days later at 9:00 AM (server timezone).</text>
                <view class="picker-row">
                    <text class="picker-label">Date</text>
                    <view class="picker-wrapper">
                        <uni-datetime-picker
                            type="date"
                            v-model="dateValue"
                            :start="minDate"
                            placeholder="Select date"
                            :border="false"
                        />
                    </view>
                </view>

                <view class="picker-row">
                    <text class="picker-label">Time</text>
                    <picker mode="time" :value="timeValue" @change="onTimeChange">
                        <view class="picker-value">
                            <view class="time-icon" />
                            <text class="picker-text">{{ timeDisplay }}</text>
                        </view>
                    </picker>
                </view>
                <button class="submit-btn" @tap="submitSchedule" :disabled="submitting">
                    {{ submitting ? 'Submitting...' : 'Confirm' }}
                </button>
            </view>
        </view>
    </view>
</template>

<script setup lang="ts">
import CommonHeader from "@/components/CommonHeader.vue";
import { ref, computed } from "vue";
import masRequest from "@/api/mas";

const dateValue = ref("");
const timeValue = ref("");
const submitting = ref(false);

const minDate = computed(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
});

const timeDisplay = computed(() => {
    if (!timeValue.value) return "Select time";
    // timeValue 通常为 HH:mm 或 HH:mm:ss
    const parts = String(timeValue.value).split(":");
    const hh = Number(parts[0]);
    const mm = parts[1] ?? "00";
    if (Number.isNaN(hh)) return timeValue.value;
    const period = hh >= 12 ? "PM" : "AM";
    const hour12 = ((hh + 11) % 12) + 1; // 0->12
    return `${hour12}:${mm} ${period}`;
});

const handleBack = () => {
    uni.navigateBack({ delta: 1 });
};

const onTimeChange = (e: any) => {
    timeValue.value = e.detail.value;
};

/** uni-datetime-picker 可能返回 string / number(时间戳) / Date，统一为 YYYY-MM-DD */
const toDateOnlyString = (v: unknown): string => {
    if (v === null || v === undefined || v === "") return "";
    const pad = (n: number) => String(n).padStart(2, "0");
    if (typeof v === "number") {
        const d = new Date(v);
        if (isNaN(d.getTime())) return "";
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    }
    if (v instanceof Date) {
        if (isNaN(v.getTime())) return "";
        return `${v.getFullYear()}-${pad(v.getMonth() + 1)}-${pad(v.getDate())}`;
    }
    const s = String(v).trim();
    const m = s.match(/^(\d{4}-\d{2}-\d{2})/);
    if (m) return m[1];
    const d = new Date(s);
    if (!isNaN(d.getTime())) {
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    }
    return "";
};

const submitSchedule = () => {
    if ((dateValue.value && !timeValue.value) || (!dateValue.value && timeValue.value)) {
        uni.showToast({ title: "Please select both date and time", icon: "none" });
        return;
    }

    let notesPayload: any[] = [{}];
    if (dateValue.value && timeValue.value) {
        // 设定了预约时间：按用户预约时间触发（OA 会校验不可早于当前时间）
        const datePart = toDateOnlyString(dateValue.value);
        if (!datePart) {
            uni.showToast({ title: "Invalid date, please select again", icon: "none" });
            return;
        }
        const t = String(timeValue.value || "").trim();
        const timePart = t.length >= 5 ? t.substring(0, 5) : "09:00";
        // 使用设备本地日历+时间生成 Date，再发 UTC ISO，避免 OA 在 Docker(UTC) 内与无时区字符串比较错误
        const local = new Date(`${datePart}T${timePart}:00`);
        if (isNaN(local.getTime())) {
            uni.showToast({ title: "Invalid date/time, please select again", icon: "none" });
            return;
        }
        const dateStr = local.toISOString();
        notesPayload = [{ date: dateStr }];
    }

    submitting.value = true;

    const reqPromise = masRequest.createSchedule({ notes: notesPayload });
    const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error("Request timeout")), 15000);
    });

    Promise.race([reqPromise, timeoutPromise])
        .then((res: any) => {
            const ok =
                res?.code === "200" ||
                res?.code === 200 ||
                String(res?.code) === "200" ||
                res?.status === "SUCCESS";
            if (ok) {
                uni.showToast({ title: "Scheduled successfully", icon: "success" });
                // 切回 Home tab，触发主页 onShow 重新拉取 next_review_time（否则留在「我的」页主页不会刷新）
                setTimeout(() => {
                    uni.switchTab({ url: "/pages/index/index" });
                }, 1200);
            } else {
                uni.showToast({ title: res?.message || "Failed to schedule", icon: "none" });
            }
        })
        .catch((err: any) => {
            uni.showToast({ title: err?.message || "Failed to schedule", icon: "none" });
        })
        .finally(() => {
            submitting.value = false;
        });
};
</script>

<style scoped lang="less">
@import url("@/less/global.less");
@import url("@/less/coach-purple.less");

.schedule-page {
    min-height: 100vh;
    background: @coach-purple-surface;
}

.schedule-content {
    padding: 24rpx 32rpx;
    min-height: calc(100vh - 120rpx);
    background: @coach-purple-surface;
    font-size: 28rpx;
    box-sizing: border-box;
}

.schedule-header-title {
    font-size: 32rpx !important;
    line-height: 44rpx !important;
    font-weight: 500;
    color: @coach-purple-900;
}

.schedule-card {
    background: rgba(255, 255, 255, 0.94);
    border: 1rpx solid rgba(124, 92, 191, 0.14);
    border-radius: 30rpx;
    padding: 36rpx 28rpx;
    box-shadow: 0 16rpx 36rpx rgba(92, 61, 158, 0.1);
    box-sizing: border-box;
    max-width: 100%;
    overflow: hidden;

    .schedule-title {
        font-size: 32rpx;
        font-weight: 600;
        color: @coach-purple-900;
        display: block;
        word-wrap: break-word;
    }

    .schedule-desc {
        font-size: 24rpx;
        color: @coach-purple-700;
        margin-top: 12rpx;
        display: block;
        line-height: 1.7;
        word-wrap: break-word;
    }

    .picker-row {
        margin-top: 40rpx;
        display: flex;
        flex-direction: column;
        align-items: stretch;
        padding: 24rpx 0;
        border-bottom: 1px solid rgba(124, 92, 191, 0.12);

        .picker-label {
            font-size: 28rpx;
            color: @coach-purple-700;
            margin-bottom: 16rpx;
            font-weight: 500;
        }

        .picker-wrapper {
            width: 100%;
        }
    }

    .picker-value {
        background: @coach-purple-50;
        border: 1px solid rgba(124, 92, 191, 0.14);
        border-radius: 20rpx;
        padding: 20rpx 24rpx;
        min-height: 72rpx;
        display: flex;
        align-items: center;
        justify-content: flex-start;
        color: @coach-purple-700;
        box-sizing: border-box;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    /* 统一 Select date / Select time 的文字样式 */
    .picker-text {
        flex: 1;
        font-size: 26rpx;
        color: @coach-purple-700;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    /* 简易时钟图标（避免依赖 uni-icons 的时钟字体） */
    .time-icon {
        width: 30rpx;
        height: 30rpx;
        border: 2rpx solid @coach-accent;
        border-radius: 50%;
        position: relative;
        box-sizing: border-box;
        flex-shrink: 0;
        margin-right: 14rpx;
    }

    .time-icon::before {
        content: '';
        position: absolute;
        left: 50%;
        top: 50%;
        width: 2rpx;
        height: 10rpx;
        background: @coach-accent;
        transform: translate(-50%, -100%) rotate(30deg);
        transform-origin: bottom center;
        border-radius: 2rpx;
    }

    .time-icon::after {
        content: '';
        position: absolute;
        left: 50%;
        top: 50%;
        width: 2rpx;
        height: 12rpx;
        background: @coach-accent;
        transform: translate(-50%, -100%) rotate(120deg);
        transform-origin: bottom center;
        border-radius: 2rpx;
    }

    /* 让 uni-datetime-picker(type="date") 的外观与原生 time picker 一致 */
    :deep(.uni-date-editor--x) {
        border: 1px solid rgba(124, 92, 191, 0.14) !important;
        border-radius: 20rpx !important;
        background: @coach-purple-50 !important;
        padding: 20rpx 24rpx !important;
        min-height: 72rpx !important;
        height: 72rpx !important;
        display: flex !important;
        align-items: center !important;
        box-sizing: border-box;
    }

    :deep(.uni-date-x),
    :deep(.uni-date__x-input) {
        background: transparent !important;
        height: 100% !important;
        display: flex !important;
        align-items: center !important;
    }

    :deep(.uni-date__x-input) {
        font-size: 26rpx !important;
        color: @coach-purple-700 !important;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    :deep(.icon-calendar) {
        color: @coach-accent !important;
    }

    .submit-btn {
        margin-top: 48rpx;
        width: 100%;
        max-width: 100%;
        height: 80rpx;
        background: linear-gradient(135deg, @coach-purple-500 0%, @coach-purple-700 100%);
        border-radius: 24rpx;
        color: #fff;
        font-size: 30rpx;
        font-weight: 600;
        display: flex;
        align-items: center;
        justify-content: center;
        box-sizing: border-box;
        box-shadow: 0 12rpx 28rpx rgba(92, 61, 158, 0.2);
    }

    .submit-btn[disabled] {
        opacity: 0.7;
    }
}
</style>
