<script setup lang="ts">
import { ref } from "vue";
import { onLaunch, onShow, onHide } from "@dcloudio/uni-app";
import chatRequest from "@/api/chat";
import masRequest from "@/api/mas";
import {
  unwrapNextReviewPayload,
  MAS_COACH_LAST_TRIGGERED_AT_KEY,
  scheduleTriggerDedupeKey,
} from "@/utils/masCoachReminder";

const xToken = ref<string | null>(null);
const StatusBar = ref<number>(0);
const CustomBar = ref<number>(0);
const Custom = ref<any>(null);

/** App 閸︺劌澧犻崣鐗堟鏉烆喛顕楅敍姝凙 閺嶅洩顔囨０鍕瀹歌尪袝閸?SOA 閸氬氦鍤滈崝銊ㄧ箻閸?MAS 閼卞﹤銇?*/
const COACH_POLL_MS = 15_000;
let coachPollTimer: ReturnType<typeof setInterval> | null = null;
/** 闂冨弶顒涢獮璺哄絺 GET next_review 閸︺劌鎮撴稉鈧潪顔荤皑娴犺泛鎯婇悳顖炲櫡闁插秴顦插☉鍫ｅ瀭閸氬奔绔寸憴锕€褰?*/
let coachScheduleHandling = false;

function getCurrentRoute(): string {
  try {
    const pages = getCurrentPages();
    if (!pages.length) return "";
    const p: any = pages[pages.length - 1];
    return p?.route || "";
  } catch {
    return "";
  }
}

function navigateToMasChatOnSchedule() {
  // Create a new MAS session when scheduler is triggered.
  chatRequest
    .sessionMasCreate()
    .then((data: any) => {
      if (data?.data?.id) {
        uni.redirectTo({
          url: `/pages/chat/index?sessionId=${data.data.id}`,
        });
        uni.showToast({
          title: "Coaching session is ready",
          icon: "none",
          duration: 2500,
        });
      } else {
        uni.showToast({
          title: "Could not open new coaching chat",
          icon: "none",
          duration: 2500,
        });
      }
    })
    .catch(() => {
      uni.showToast({
        title: "Could not open new coaching chat",
        icon: "none",
        duration: 2500,
      });
    });
}

function pollMasCoachAppointmentTrigger() {
  if (!uni.getStorageSync("x-token")) return;
  const route = getCurrentRoute();
  if (route === "pages/login/index") return;

  masRequest
    .getNextReviewTime()
    .then((res: any) => {
      const payload = unwrapNextReviewPayload(res);
      const fired =
        payload?.triggered === true ||
        payload?.triggered === "true" ||
        payload?.triggered === 1;
      const at = payload?.triggered_at;
      if (!fired || at == null || at === "") return;

      const dedupeKey = scheduleTriggerDedupeKey(at);
      if (!dedupeKey) return;

      const prev = uni.getStorageSync(MAS_COACH_LAST_TRIGGERED_AT_KEY);
      if (prev === dedupeKey) return;
      if (coachScheduleHandling) return;
      coachScheduleHandling = true;
      try {
        uni.setStorageSync(MAS_COACH_LAST_TRIGGERED_AT_KEY, dedupeKey);

        // 缂佺喍绔寸挧鎷岀儲鏉烆剟鈧槒绶敍灞藉瑏閸氭垼浜版径鈺呫€?emit閿涙ventBus.on 娴?push 閸ョ偠鐨熼敍宀勩€夐棃銏＄垽/redirect 閺冭泛褰查懗鑺ユ弓 off閿?        // 鐎佃壈鍤ф稉鈧▎陇袝閸欐垵顦垮▎?sessionMasCreate閿涘瞼鈹栨导姘崇樈閸欏秴顦查幏?greeting閵?        navigateToMasChatOnSchedule();
      } finally {
        coachScheduleHandling = false;
      }
    })
    .catch(() => {});
}

onLaunch(() => {
  if (typeof uni.setLocale === "function") {
    uni.setLocale("en");
  }
});

onShow(() => {
  if (coachPollTimer) {
    clearInterval(coachPollTimer);
    coachPollTimer = null;
  }
  coachPollTimer = setInterval(pollMasCoachAppointmentTrigger, COACH_POLL_MS);
  pollMasCoachAppointmentTrigger();
});

onHide(() => {
  if (coachPollTimer) {
    clearInterval(coachPollTimer);
    coachPollTimer = null;
  }
});
</script>
<style></style>