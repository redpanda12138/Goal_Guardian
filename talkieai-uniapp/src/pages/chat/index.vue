<template>
  <view class="chat-box">
    <CommonHeader background-color="#fff" :leftIcon='true' :back-fn="handleBackPage" title="Chat">
      <template v-slot:content>
        <view class="header-title">Chat</view>
      </template>
      <template v-slot:right>
        <view v-if="session.type === 'MAS' || isHistoryView" class="header-history-btn" @tap="openHistoryDrawer">
          <text class="header-history-text">History</text>
        </view>
      </template>
    </CommonHeader>

    <!-- MAS会话操作按钮（在header下方），历史查看模式下不显示 -->
    <view v-if="session.type === 'MAS' && !isHistoryView" class="mas-top-actions" :style="{ top: headerTop + 'px' }">
      <view class="action-btn-box" @tap="handleStartNewSession">
        <text class="action-btn-text">New Session</text>
      </view>
    </view>

    <!-- 聊天内容 -->
    <view class="chat-container" :class="{ 'chat-container--mas': session.type === 'MAS' && !isHistoryView }">
      <view v-if="session.type === 'MAS' && !isHistoryView" class="mas-coach-dash">
        <CoachDashboardCards
          :dashboard="coachDashboard"
          :loading="coachDashboardLoading"
          merged
          @mark-complete="onCoachMarkComplete"
          @modify="onCoachModify"
          @next-tap="onCoachNextTap"
        />
      </view>
      <template v-for="(message, index) in messages" :key="message.id">
        <view class="message-content-item">
          <message-content :auto-hint="messages.auto_text_shadow" :auto-play="accountSetting.auto_playing_voice"
            :auto-pronunciation="accountSetting.auto_pronunciation" :message="message"
            ref="messageListRef"></message-content>
        </view>
      </template>
    </view>

    <!-- 底部操作栏：历史查看模式下不显示 -->
    <view class="chat-bottom-container" v-if="!isMasSessionCompleted && !isHistoryView">
      <!-- 键盘输入 -->
      <view v-if="!inputTypeVoice" class="input-bottom-container" :style="'bottom:' + inputBottom + 'px;'">
        <view @tap="handleSwitchInputType" class="voice-icon-box">
          <image class="voice-icon" src="/static/icon_voice_fixed.png"></image>
        </view>
        <view v-if="lastRecordedFileName" @tap="playLastRecording" class="play-record-icon-box" title="Play recorded audio">
          <image class="play-record-icon" src="/static/icon_menu_play.png"></image>
        </view>
        <view class="input-box">
          <textarea
            class="textarea"
            v-model="inputText"
            :style="{ height: textareaHeightRpx + 'rpx' }"
            placeholder="Input here"
            @focus="inputFocus"
            @input="handleInput"
            @confirm="handleSendText"
            confirm-type="send"
            :auto-height="false"
            :show-confirm-bar="true"
          />
        </view>
        <view @tap="handleSendText" class="send-icon-box" :class="{ active: inputHasText }">
          <image class="send-icon" src="/static/icon_send.png"> </image>
        </view>
      </view>

      <view v-if="inputTypeVoice">
        <!-- 提示 -->
        <prompt :sessionId="session.id" v-if="menuSwitchDown"></prompt>

        <!-- 语音输入：录音后自动转译，左删中播右发，下方为可编辑转译文字 -->
        <view class="speech-box">
          <Speech
            :session-id="session.id"
            @completed="onVoiceRecordingCompleted"
            @delete="onVoiceDelete"
            @send="handleVoiceSend"
          >
            <template v-slot:leftMenu>
              <image @tap="handleSwitchInputType" class="keybord-icon" src="/static/icon_keybord.png"></image>
            </template>
            <template v-slot:rightMenu>
              <image @tap="handleSwitchMenu" class="input-type-switch-btn" src="/static/icon_settings.png"></image>
            </template>
          </Speech>
          <!-- 录音完成后的文字编辑栏（与键盘输入栏样式一致） -->
          <view v-if="lastRecordedFileName" class="voice-mode-textarea-wrap">
            <textarea
              v-model="voiceTranscribedText"
              class="textarea voice-mode-textarea"
              placeholder="Transcription will appear here, you can edit before sending."
              :disabled="voiceTranscribing"
            />
          </view>
        </view>
      </view>
    </view>

    <!-- 历史记录侧栏 -->
    <view v-if="showHistoryDrawer" class="history-drawer-mask" @tap="closeHistoryDrawer"></view>
    <view class="history-drawer" :class="{ 'history-drawer-open': showHistoryDrawer }">
      <view class="history-drawer-header">
        <text class="history-drawer-title">Chat History</text>
        <view class="history-drawer-close" @tap="closeHistoryDrawer">
          <text>×</text>
        </view>
      </view>
      <scroll-view v-if="historySessions.length" class="history-drawer-list" scroll-y>
        <view
          v-for="item in historySessions"
          :key="item.id"
          class="history-drawer-item"
          :class="{ 'history-drawer-item-current': item.id === session.id }"
          @tap="onHistoryDrawerItemTap(item)"
        >
          <view class="history-drawer-item-body">
            <view class="history-drawer-item-row">
              <text class="history-drawer-item-time">{{ item.friendly_time || item.create_time }}</text>
              <text v-if="item.id === currentSessionId" class="history-drawer-item-badge">Current chat</text>
            </view>
            <text class="history-drawer-item-msg">{{ item.message_count || 0 }} messages</text>
            <text v-if="item.completed === 1" class="history-drawer-item-done">Completed</text>
          </view>
          <view
            v-if="historyDeleteMode"
            class="history-drawer-select-wrap"
            @tap.stop="toggleHistorySelect(item)"
          >
            <view
              v-if="item.completed !== 1"
              class="history-drawer-checkbox"
              :class="{ 'history-drawer-checkbox-checked': historySelectedIds.includes(item.id) }"
            >
              <text v-if="historySelectedIds.includes(item.id)" class="history-drawer-checkmark">✓</text>
            </view>
            <text v-else class="history-drawer-select-skip">—</text>
          </view>
        </view>
      </scroll-view>
      <view v-else class="history-drawer-empty">
        <text>No Chat History</text>
      </view>
      <view v-if="historySessions.length" class="history-drawer-footer">
        <template v-if="!historyDeleteMode">
          <view class="history-drawer-delete-btn" @tap="startHistoryDeleteMode">
            <text class="history-drawer-delete-text">Delete</text>
          </view>
        </template>
        <view v-else class="history-drawer-footer-btns">
          <view class="history-drawer-btn-cancel" @tap="cancelHistoryDeleteMode">
            <text>Cancel</text>
          </view>
          <view class="history-drawer-btn-confirm" @tap="onHistoryDeleteConfirmClick">
            <text>Confirm</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import CommonHeader from "@/components/CommonHeader.vue";
import CoachDashboardCards from "@/components/CoachDashboardCards.vue";
import MessageContent from "./components/MessageContent.vue";
import Prompt from "./components/Prompt.vue";
import Speech from "./components/MessageSpeech.vue";
import { ref, computed, nextTick, onMounted, onBeforeUnmount, getCurrentInstance } from "vue";
import { onLoad, onShow } from "@dcloudio/uni-app";
import chatRequest from "@/api/chat";
import masRequest from "@/api/mas";
import accountRequest from "@/api/account";
import topicRequest from "@/api/topic";
import utils from "@/utils/utils";
import audioPlayer from "@/components/audioPlayerExecuter";
import type { Message, MessagePage, Session, AccountSettings } from "@/models/models";

const session = ref<Session>({
  id: undefined,
  type: undefined,
  messages: { total: 0, list: [] } as MessagePage,
});
const messages = ref<Message[]>([]);
const inputTypeVoice = ref(true);
const inputText = ref("");
/** 当前待发送的录音文件名（录音完成后保留；删除/发送后清空） */
const lastRecordedFileName = ref<string | null>(null);
/** 语音模式下、录音完成后的转译文字（可编辑），显示在下方文字栏 */
const voiceTranscribedText = ref("");
/** 是否正在转译（转译中时下方文字栏禁用输入） */
const voiceTranscribing = ref(false);
const menuSwitchDown = ref(true);
const inputBottom = ref(0)
// 输入框高度（rpx）：根据内容在 1～6 行间变化，删除文字时会缩回
const textareaHeightRpx = ref(80);
const TEXTAREA_LINE_HEIGHT = 42;
const TEXTAREA_CHARS_PER_LINE = 22;
const TEXTAREA_MIN_HEIGHT = 80;
const TEXTAREA_MAX_HEIGHT = 300;

const messageListRef = ref([]);
const accountSetting = ref<AccountSettings>({
  auto_playing_voice: 0,
  auto_text_shadow: 0,
  auto_pronunciation: 0,
  playing_voice_speed: '1.0',
  speech_role_name_label: '',
  speech_role_name: '',
  target_language: '',
})

// MAS会话状态
const isMasSessionCompleted = ref(false);
const coachDashboard = ref<Record<string, any> | null>(null);
const coachDashboardLoading = ref(false);

// 历史查看模式：从侧栏进入的只读对话，不显示输入栏与 New Session
const isHistoryView = ref(false);

// 历史记录侧栏
const showHistoryDrawer = ref(false);
const historySessions = ref<
  { id: string; create_time?: string; friendly_time?: string; message_count?: number; completed?: number }[]
>([]);
// 当前可继续聊天的会话 id（会话列表按时间倒序，取最新一条），点击该项时不带 history=1，会显示输入栏
const currentSessionId = ref<string | undefined>(undefined);
const historyDeleteMode = ref(false);
const historySelectedIds = ref<string[]>([]);

// Header高度，用于定位New Session按钮
const headerTop = ref(0);

const $bus: any = getCurrentInstance()?.appContext.config.globalProperties.$bus;

const inputFocus = (e: any) => {
  inputBottom.value = e.detail.height;
}

// 是否已经输入文本
const inputHasText = computed(() => {
  return !!(inputText.value && inputText.value.trim());
});

const sendMessageHandler = (info: any) => {
  if (info.text) {
    sendMessage(info.text, info.fileName);
  } else if (info.fileName) {
    lastRecordedFileName.value = info.fileName;
    transcribeVoiceToText(info.fileName);
  }
};

/** 预约到点由 App.vue 直接 navigateToMasChatOnSchedule，避免 EventBus 重复订阅 */

/** initData 并发/快速切换会话时丢弃过期请求，避免多次写入同一会话 greeting */
let chatInitEpoch = 0;

onLoad((option: any) => {
  isHistoryView.value = option.history === '1' || option.history === 'true';
  initData(option.sessionId);
  uni.setNavigationBarTitle({
    title: isHistoryView.value ? 'Chat History' : 'TalkieAI'
  });
  
  // 计算header高度，用于定位New Session按钮
  const instance = getCurrentInstance();
  const CustomBar = instance?.appContext.config.globalProperties.CustomBar || 88;
  const StatusBar = instance?.appContext.config.globalProperties.StatusBar || 0;
  headerTop.value = CustomBar + StatusBar;
  
  console.log('Onload')
  $bus.on("SendMessage", sendMessageHandler);
});

onMounted(() => {
});

onBeforeUnmount(() => {
  $bus.off("SendMessage", sendMessageHandler);
});

onShow(() => {
  // 获取用户配置
  accountRequest.getSettings().then((data) => {
    accountSetting.value = data.data;
  });
  
  // 如果是MAS会话，检查会话状态
  if (session.value.type === 'MAS' && session.value.id) {
    checkMasSessionStatus();
    loadCoachDashboard();
  }
});

const loadCoachDashboard = () => {
  if (session.value.type !== "MAS" || isHistoryView.value || !session.value.id) {
    return;
  }
  coachDashboardLoading.value = true;
  masRequest
    .getCoachDashboard()
    .then((res: any) => {
      coachDashboard.value = res?.data ?? null;
    })
    .catch(() => {
      coachDashboard.value = null;
    })
    .finally(() => {
      coachDashboardLoading.value = false;
    });
};

const onCoachMarkComplete = (goalIndex: number) => {
  masRequest
    .postCoachStateEvent({ event_type: "goal_completed", goal_index: goalIndex })
    .then((res: any) => {
      coachDashboard.value = res?.data?.dashboard ?? coachDashboard.value;
      messages.value.push({
        id: `se_${Date.now()}`,
        session_id: session.value.id,
        content: `Status update: Goal ${goalIndex + 1} has been marked complete.`,
        owner: false,
        role: "ASSISTANT",
        style: "STATE_EVENT:goal_completed",
        message_kind: "state_event",
        file_name: null,
        auto_hint: false,
        auto_play: false,
        auto_pronunciation: false,
      });
      nextTick(() => scrollToBottom());
    })
    .catch(() => uni.showToast({ title: "Update failed", icon: "none" }));
};

const onCoachModify = () => {
  uni.navigateTo({ url: "/pages/my/schedule" });
};

const onCoachNextTap = () => {
  uni.switchTab({ url: "/pages/practice/index" });
};

/** 根据内容计算输入框高度（1～6 行），删除文字时能缩回一行 */
function updateTextareaHeight() {
  const text = inputText.value || "";
  if (!text.trim()) {
    textareaHeightRpx.value = TEXTAREA_MIN_HEIGHT;
    return;
  }
  const lines = text.split("\n");
  let totalLines = 0;
  for (const line of lines) {
    totalLines += Math.max(1, Math.ceil(line.length / TEXTAREA_CHARS_PER_LINE));
  }
  const h = totalLines * TEXTAREA_LINE_HEIGHT;
  textareaHeightRpx.value = Math.min(TEXTAREA_MAX_HEIGHT, Math.max(TEXTAREA_MIN_HEIGHT, h));
}

/**
 * 如果用户输入回车，则发送消息
 */
const handleInput = (event: any) => {
  nextTick(updateTextareaHeight);
  if (event.keyCode === 13) {
    handleSendText();
  }
}

/**
 * 发送文本（只发文字内容，不发语音文件；若有待发送录音则清空）
 */
const handleSendText = () => {
  if (!inputHasText.value) {
    return;
  }
  const inputTextValue = inputText.value;
  inputText.value = "";
  textareaHeightRpx.value = TEXTAREA_MIN_HEIGHT;
  lastRecordedFileName.value = null;
  sendMessage(inputTextValue);
};

/** 播放当前已录制的语音（转录后、发送前可听） */
const playLastRecording = () => {
  if (!lastRecordedFileName.value) return;
  audioPlayer.playAudio({
    audioUrl: utils.getVoiceFileUrl(lastRecordedFileName.value),
    listener: {
      playing: () => {},
      success: () => {},
      error: () => {
        uni.showToast({ title: 'Playback failed', icon: 'none' });
      },
    },
  });
};

/**
 * 对提示、翻译的功能进行隐藏\显示的切换
 */
const handleSwitchMenu = () => {
  uni.navigateTo({
    url: `/pages/chat/settings?sessionId=${session.value.id}`,
  });
  // menuSwitchDown.value = !menuSwitchDown.value;
};

/** 录音完成：立即执行转译，结果填入下方文字栏（不切换模式） */
const onVoiceRecordingCompleted = (payload: { fileName: string }) => {
  if (!payload?.fileName) return;
  lastRecordedFileName.value = payload.fileName;
  voiceTranscribedText.value = "";
  transcribeVoiceToTextForVoiceMode(payload.fileName);
};

/** 删除当前录音并清空下方文字栏 */
const onVoiceDelete = () => {
  lastRecordedFileName.value = null;
  voiceTranscribedText.value = "";
};

/** 发送下方文字栏内容（仅发文字），然后清空状态 */
const handleVoiceSend = () => {
  const text = (voiceTranscribedText.value || "").trim();
  sendMessage(text || "");
  lastRecordedFileName.value = null;
  voiceTranscribedText.value = "";
};

/**
 * 语音模式专用：转译后只填入 voiceTranscribedText，不切换输入模式
 */
const transcribeVoiceToTextForVoiceMode = (fileName: string) => {
  voiceTranscribing.value = true;
  uni.showLoading({ title: "Recognizing...", mask: true });

  chatRequest
    .transformText({ file_name: fileName, sessionId: session.value.id })
    .then((data) => {
      uni.hideLoading();
      voiceTranscribing.value = false;
      const text = data.data?.transcribed_text;
      if (text != null && String(text).trim()) {
        voiceTranscribedText.value = String(text).trim();
        uni.showToast({ title: "Recognition complete", icon: "success", duration: 1500 });
      } else {
        voiceTranscribedText.value = "";
        uni.showToast({ title: "No speech detected", icon: "none" });
      }
    })
    .catch((err) => {
      uni.hideLoading();
      voiceTranscribing.value = false;
      console.error("语音转文字失败:", err);
      uni.showToast({ title: "Recognition failed", icon: "none" });
    });
};

/**
 * 将语音识别结果填入文本框（用于键盘模式或 SendMessage 等）
 */
const transcribeVoiceToText = (fileName: string) => {
  uni.showLoading({ title: "Recognizing...", mask: true });
  chatRequest
    .transformText({ file_name: fileName, sessionId: session.value.id })
    .then((data) => {
      uni.hideLoading();
      const text = data.data?.transcribed_text;
      if (text != null && String(text).trim()) {
        inputText.value = String(text).trim();
        inputTypeVoice.value = false;
        uni.showToast({ title: "Recognition complete", icon: "success", duration: 1500 });
      } else {
        uni.showToast({ title: "No speech detected", icon: "none" });
      }
    })
    .catch((err) => {
      uni.hideLoading();
      console.error("语音转文字失败:", err);
      uni.showToast({ title: "Recognition failed", icon: "none" });
    });
};

/**
 * 发送语音消息（直接发送，不填入文本框）
 */
const sendSpeech = (fileName: string) => {
  const ownertTimestamp = new Date().getTime();
  const ownMessage: any = {
    id: ownertTimestamp,
    content: null,
    owner: true,
    file_name: fileName,
    role: "USER",
    auto_hint: false,
    auto_play: false,
  };
  messages.value.push(ownMessage);

  scrollToBottom();

  // 使用新的语音转文字接口
  chatRequest.transformText({ file_name: fileName, sessionId: session.value.id })
    .then(data => {
      messages.value = messages.value.filter(
        (item) => (item.id as any) !== ownertTimestamp
      );
      let text = data.data.transcribed_text; // 注意：现在返回的是对象格式
      console.log(text);
      sendMessage(text, fileName)
    })
    .catch(error => {
      console.error('语音转文字失败:', error);
      uni.showToast({
        title: 'Recognition failed',
        icon: 'none'
      });
      // 移除临时消息
      messages.value = messages.value.filter(
        (item) => (item.id as any) !== ownertTimestamp
      );
    });
}

/**
 * 发送文字消息
 * @param message 消息内容
 * @param fileName 如果是语音发送, 则传入文件名
 */
const sendMessage = (message?: string, fileName?: string) => {
  console.log('send file name');
  const ownertTimestamp = new Date().getTime();
  const ownMessage: any = {
    id: ownertTimestamp,
    session_id: session.value.id,
    content: message,
    owner: true,
    file_name: fileName,
    role: "USER",
    auto_hint: false,
    auto_play: false,
    auto_pronunciation: false,
  };
  messages.value.push(ownMessage);
  // 防止跟前面的timestamp一样
  const timestamp = new Date().getTime() + 1;
  const aiMessage: any = {
    id: timestamp,
    session_id: session.value.id,
    content: null,
    owner: false,
    file_name: null,
    role: "ASSISTANT",
    auto_hint: false,
    auto_play: false,
    auto_pronunciation: false,
  };
  messages.value.push(aiMessage);
  scrollToBottom();
  chatRequest
    .sessionChatInvoke({
      sessionId: session.value.id,
      message: message,
      file_name: fileName,
    })
    .then((data) => {
      data = data.data;
      messages.value = messages.value.filter(
        (item) => (item.id as any) !== timestamp && (item.id as any) !== ownertTimestamp
      );

      ownMessage.id = data.send_message_id;
      ownMessage.auto_pronunciation = true;
      messages.value.push({
        ...ownMessage,
      });

      messages.value.push({
        ...aiMessage,
        id: data.id,
        content: data.data,
        auto_hint: accountSetting.value.auto_text_shadow == 1,
        auto_play: accountSetting.value.auto_playing_voice == 1,
      });

      // AI消息自动播放与模糊
      nextTick(() => {
        scrollToBottom();
      });
      
      // 检查MAS会话是否已完成
      if (session.value.type === 'MAS') {
        if (data.completed) {
          isMasSessionCompleted.value = true;
        } else {
          // 即使没有completed标志，也检查一下状态
          checkMasSessionStatus();
        }
        loadCoachDashboard();
      }
      // 录音识别发送成功后删除服务器上的录音文件
      if (fileName) {
        chatRequest.voiceFileDelete(fileName).catch(() => {});
      }
    })
    .catch((e) => {
      // 为用户提示错误show toast
      uni.showToast({
        title: 'fail to send..',
        icon: "none",
      });
      console.error(e);
      messages.value.pop();
      messages.value.pop();
    });
};

// 切换输入方式
const handleSwitchInputType = () => {
  inputTypeVoice.value = !inputTypeVoice.value;
};

/**
 * 初始化聊天数据
 * @param sessionId
 */
const initData = (sessionId: string) => {
  const epoch = ++chatInitEpoch;
  // 先清空消息列表，避免从上一会话跳转过来时仍显示旧消息（如 New Session 后第一次显示成上一条会话的第二条）
  messages.value = [];
  chatRequest.sessionDetailsGet({ sessionId }).then((res: any) => {
    if (epoch !== chatInitEpoch) return;
    session.value = res.data;
    // 如果没有任何历史消息，则请求后台生成第一条消息
    if (session.value.messages.total === 0) {
      // 历史查看模式下只读，不应触发初始化问候语写入，避免历史会话被改写成1条
      if (isHistoryView.value) {
        return;
      }
      const timestamp = new Date().getTime();
      const aiMessage: any = {
        id: timestamp,
        session_id: session.value.id,
        content: null,
        owner: false,
        file_name: null,
        role: "ASSISTANT",
        auto_hint: false,
        auto_play: false,
        auto_pronunciation: false,
      };
      messages.value.push(aiMessage);
      chatRequest.sessionInitGreeting(sessionId).then((res: any) => {
        if (epoch !== chatInitEpoch) return;
        messages.value.pop();
        session.value.messages.list.push(res.data)
        messages.value.push({
          id: res.data.id,
          session_id: res.data.session_id,
          content: res.data.content,
          role: res.data.role,
          owner: res.data.role === "USER",
          style: res.data.style,
          message_kind: res.data.message_kind,
          auto_hint: accountSetting.value.auto_text_shadow == 1,
          auto_play: accountSetting.value.auto_playing_voice == 1,
          auto_pronunciation: false,
          pronunciation: null
        });
        // AI消息自动播放与模糊
        nextTick(() => {
          scrollToBottom();
        });
      })
      return;
    }

    session.value.messages.list.forEach((item) => {
      messages.value.push({
        id: item.id,
        session_id: item.session_id,
        content: item.content,
        role: item.role,
        owner: item.role === "USER",
        file_name: item.file_name,
        style: (item as any).style,
        message_kind: (item as any).message_kind,
        auto_hint: false,
        auto_play: false,
        auto_pronunciation: false,
        pronunciation: item.pronunciation
      });
    });
    scrollToBottom();
    
    // 如果是MAS会话，检查会话状态
    if (session.value.type === 'MAS') {
      console.log("MAS session detected, checking status...");
      checkMasSessionStatus();
      loadCoachDashboard();
    } else {
      console.log("Session type:", session.value.type, "- not MAS, skipping status check");
    }
  });
};

/**
 * 检查MAS会话状态
 */
const checkMasSessionStatus = () => {
  console.log("Checking MAS session status, session type:", session.value.type);
  if (session.value.type !== 'MAS') {
    console.log("Not a MAS session, skipping status check");
    return;
  }
  
  chatRequest.sessionMasGetCurrent().then((statusData) => {
    console.log("Current MAS session status response:", JSON.stringify(statusData));
    const sessionStatus = statusData?.data?.session_status;
    console.log("Extracted session_status:", sessionStatus);
    isMasSessionCompleted.value = sessionStatus === "completed";
    console.log("isMasSessionCompleted set to:", isMasSessionCompleted.value);
  }).catch((e) => {
    console.error("Failed to get MAS session status:", e);
    // 如果获取失败，不显示按钮
    isMasSessionCompleted.value = false;
  });
};

/**
 * 继续之前的会话（进入列表中最新一条，不 get-or-create）
 */
const handleContinueSession = () => {
  chatRequest.sessionMasList().then((res: any) => {
    const list = res?.data;
    const id =
      Array.isArray(list) && list.length > 0 ? (list[0] as { id?: string })?.id : null;
    if (id) {
      uni.redirectTo({
        url: `/pages/chat/index?sessionId=${id}`,
      });
      return;
    }
    uni.showToast({
      title: "No session to continue",
      icon: "none",
      duration: 2500,
    });
  }).catch((e) => {
    console.error("Failed to list MAS sessions:", e);
    const errorMsg = e?.detail || e?.message || "Unknown error";
    uni.showToast({
      title: `Failed: ${errorMsg}`,
      icon: "none",
      duration: 3000,
    });
  });
};

/** 打开历史记录侧栏 */
const openHistoryDrawer = () => {
  showHistoryDrawer.value = true;
  historyDeleteMode.value = false;
  historySelectedIds.value = [];
  currentSessionId.value = undefined;
  chatRequest
    .sessionMasList()
    .then((listRes: any) => {
      const list = (listRes?.data || []) as typeof historySessions.value;
      historySessions.value = list;
      currentSessionId.value =
        Array.isArray(listRes?.data) && listRes.data.length > 0
          ? (listRes.data[0] as { id?: string })?.id
          : undefined;
    })
    .catch((e) => {
      console.error("Load MAS session list failed:", e);
      uni.showToast({ title: "Load history failed", icon: "none" });
    });
};

/** 关闭历史记录侧栏 */
const closeHistoryDrawer = () => {
  showHistoryDrawer.value = false;
  historyDeleteMode.value = false;
  historySelectedIds.value = [];
};

const startHistoryDeleteMode = () => {
  historyDeleteMode.value = true;
  historySelectedIds.value = [];
};

const cancelHistoryDeleteMode = () => {
  historyDeleteMode.value = false;
  historySelectedIds.value = [];
};

const toggleHistorySelect = (item: { id: string; completed?: number }) => {
  if (item.completed === 1) return;
  const i = historySelectedIds.value.indexOf(item.id);
  if (i >= 0) {
    historySelectedIds.value = historySelectedIds.value.filter((x) => x !== item.id);
  } else {
    historySelectedIds.value = [...historySelectedIds.value, item.id];
  }
};

const onHistoryDrawerItemTap = (item: { id: string; completed?: number }) => {
  if (historyDeleteMode.value) {
    toggleHistorySelect(item);
    return;
  }
  selectHistorySession(item);
};

const onHistoryDeleteConfirmClick = () => {
  const ids = historySelectedIds.value.filter(Boolean);
  if (!ids.length) {
    uni.showToast({ title: "Select conversations to delete", icon: "none" });
    return;
  }
  uni.showModal({
    title: "Delete conversations",
    content: `Permanently delete ${ids.length} incomplete conversation(s)? This cannot be undone.`,
    confirmText: "Delete",
    cancelText: "Back",
    success: (res) => {
      if (res.confirm) {
        runHistoryDelete(ids);
      }
    },
  });
};

const runHistoryDelete = (ids: string[]) => {
  uni.showLoading({ title: "Deleting...", mask: true });
  chatRequest
    .sessionMasDeleteBulk({ session_ids: ids })
    .then((res: any) => {
      uni.hideLoading();
      const deleted: string[] = res?.data?.deleted || [];
      const failed = res?.data?.failed || [];
      if (failed.length && !deleted.length) {
        uni.showToast({
          title: failed[0]?.reason || "Delete failed",
          icon: "none",
          duration: 2500,
        });
        return;
      }
      if (failed.length) {
        uni.showToast({
          title: `Deleted ${deleted.length}, some skipped`,
          icon: "none",
          duration: 2500,
        });
      } else {
        uni.showToast({ title: "Deleted", icon: "success", duration: 1500 });
      }
      cancelHistoryDeleteMode();
      chatRequest.sessionMasList().then((listRes: any) => {
        const list = (listRes?.data || []) as typeof historySessions.value;
        historySessions.value = list;
        currentSessionId.value =
          Array.isArray(list) && list.length > 0 ? list[0].id : undefined;
        const sid = session.value.id;
        if (sid && deleted.includes(sid)) {
          if (list.length && list[0]?.id) {
            uni.redirectTo({
              url: `/pages/chat/index?sessionId=${list[0].id}`,
            });
          } else {
            uni.switchTab({ url: "/pages/index/index" });
          }
        }
      });
    })
    .catch((e) => {
      uni.hideLoading();
      console.error(e);
      const detail = (e as any)?.detail;
      const msg =
        detail === "Not Found" || detail === "not found"
          ? "The delete endpoint is unavailable. Please update the backend and restart the service."
          : (e as any)?.message || (typeof detail === "string" ? detail : "") || "Delete failed";
      uni.showToast({
        title: msg,
        icon: "none",
      });
    });
};

/** 选择历史会话：若是“当前会话”则带输入栏，否则进入只读对话页 */
const selectHistorySession = (item: { id: string }) => {
  closeHistoryDrawer();
  if (item.id === session.value.id && !isHistoryView.value) {
    return;
  }
  // 最近一条未完成的聊天（当前会话）：不带 history=1，会显示输入栏
  const isCurrentSession = item.id === currentSessionId.value;
  const url = isCurrentSession
    ? `/pages/chat/index?sessionId=${item.id}`
    : `/pages/chat/index?sessionId=${item.id}&history=1`;
  uni.redirectTo({ url });
};

/**
 * 开始新会话
 */
const handleStartNewSession = () => {
  chatRequest.sessionMasCreate().then((data) => {
    console.log("New MAS session:", data);
    if (data && data.data && data.data.id) {
      // 跳转到新会话
      uni.redirectTo({
        url: `/pages/chat/index?sessionId=${data.data.id}`,
      });
    } else {
      console.error("Invalid MAS session data:", data);
      uni.showToast({
        title: "Failed to create MAS session: data format error",
        icon: "none",
        duration: 3000,
      });
    }
  }).catch((e) => {
    console.error("Failed to create MAS session:", e);
    const errorMsg = e?.detail || e?.message || "Unknown error";
    uni.showToast({
      title: `Failed to create MAS session: ${errorMsg}`,
      icon: "none",
      duration: 3000,
    });
  });
};

/**
 * 回到主页面
 */
const handleBackPage = () => {
  const fallbackToTopLevel = () => {
    // 页面栈不足时兜底回一级 tab 页面，避免“返回无响应”
    uni.switchTab({
      url: "/pages/index/index",
    });
  };

  // 如果是话题的话，提示用户是否结束些次话题
  if (session.value.type === 'TOPIC') {
    uni.showModal({
      title: 'Finish this topic?',
      content: 'Do you want to finish and score this topic now?',
      success: (res) => {
        if (res.confirm) {
          completeTopic();
        } else if (res.cancel) {
          const pages = getCurrentPages();
          if (pages.length > 1) {
            uni.navigateBack({
              fail: () => fallbackToTopLevel(),
            });
          } else {
            fallbackToTopLevel();
          }
        }
      },
    });
  } else {
    const pages = getCurrentPages();
    if (pages.length > 1) {
      uni.navigateBack({
        fail: () => fallbackToTopLevel(),
      });
    } else {
      fallbackToTopLevel();
    }
  }
};

const completeTopic = () => {
  topicRequest.completeTopic({ session_id: session.value.id })
    .then((res) => {
      uni.navigateTo({
        url: `/pages/topic/completion?sessionId=${session.value.id}&redirectType=index`
      });
    });
}

/**
 * 滚动到最底部
 */
const scrollToBottom = () => {
  // 获取scroll-view实例
  if (messages.value.length === 0) {
    return;
  }
  // h5页面直接最原始的API
  nextTick(() => {
    uni.pageScrollTo({
      scrollTop: 10000,
      duration: 100,
    });
  });
};
</script>

<style lang="less" scoped>
@import url("@/less/coach-purple.less");
.chat-box {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 100vh;
  background: @coach-purple-surface;
}

.chat-container {
  width: 90%;
  height: 100%;
  max-width: 900px;
  margin: 0 auto;
  box-sizing: border-box;
  padding-bottom: 400rpx;
  padding-top: 80rpx;

  &.chat-container--mas {
    padding-top: 140rpx;
  }

  .mas-coach-dash {
    width: 100%;
    margin-bottom: 8rpx;
  }

  .message-content-item {
    margin-top: 45rpx;
  }

  .message-content-item:first-child {
    margin-top: 24rpx;
  }
}

.header-title {
  font-size: 36rpx;
  font-weight: 500;
  color: @coach-purple-900;
}

.header-history-btn {
  padding: 10rpx 8rpx 10rpx 18rpx;
  background: transparent;
  border: none;
  box-shadow: none;
  .header-history-text {
    font-size: 28rpx;
    color: @coach-purple-700;
    font-weight: 500;
  }
}

.history-drawer-mask {
  position: fixed;
  left: 0;
  top: 0;
  right: 0;
  bottom: 0;
  background: rgba(45, 31, 71, 0.18);
  z-index: 998;
  transition: opacity 0.2s;
}

.history-drawer {
  position: fixed;
  top: 0;
  right: 0;
  width: 75%;
  max-width: 400rpx;
  height: 100%;
  background: linear-gradient(180deg, #ffffff 0%, @coach-purple-surface 100%);
  z-index: 999;
  box-shadow: -12rpx 0 32rpx rgba(92, 61, 158, 0.18);
  transform: translateX(100%);
  transition: transform 0.25s ease;
  display: flex;
  flex-direction: column;

  &.history-drawer-open {
    transform: translateX(0);
  }
}

.history-drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 32rpx 24rpx;
  border-bottom: 1rpx solid rgba(124, 92, 191, 0.12);
}

.history-drawer-title {
  font-size: 32rpx;
  font-weight: 500;
  color: @coach-purple-900;
}

.history-drawer-close {
  width: 56rpx;
  height: 56rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 44rpx;
  color: @coach-purple-700;
}

.history-drawer-list {
  flex: 1;
  height: 0;
  min-height: 0;
  padding: 16rpx 0;
}

.history-drawer-item {
  padding: 24rpx 20rpx 24rpx 24rpx;
  border-bottom: 1rpx solid rgba(124, 92, 191, 0.08);
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 16rpx;

  &.history-drawer-item-current {
    background: rgba(232, 224, 244, 0.6);
  }
}

.history-drawer-item-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.history-drawer-item-done {
  font-size: 22rpx;
  color: @coach-purple-700;
}

.history-drawer-select-wrap {
  flex-shrink: 0;
  width: 44rpx;
  height: 44rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.history-drawer-checkbox {
  width: 36rpx;
  height: 36rpx;
  border-radius: 8rpx;
  border: 2rpx solid rgba(124, 92, 191, 0.45);
  box-sizing: border-box;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;

  &.history-drawer-checkbox-checked {
    background: @coach-purple-700;
    border-color: @coach-purple-700;
  }
}

.history-drawer-checkmark {
  font-size: 24rpx;
  color: #fff;
  line-height: 1;
}

.history-drawer-select-skip {
  font-size: 28rpx;
  color: @coach-purple-300;
}

.history-drawer-item-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
}

.history-drawer-item-time {
  font-size: 28rpx;
  color: @coach-purple-900;
  flex: 1;
}

.history-drawer-item-badge {
  font-size: 22rpx;
  color: @coach-accent;
  background: rgba(232, 224, 244, 0.95);
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
}

.history-drawer-item-msg {
  font-size: 24rpx;
  color: @coach-purple-700;
}

.history-drawer-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: @coach-purple-700;
  font-size: 28rpx;
}

.history-drawer-footer {
  flex-shrink: 0;
  padding: 20rpx 24rpx;
  padding-bottom: calc(20rpx + env(safe-area-inset-bottom));
  border-top: 1rpx solid rgba(124, 92, 191, 0.12);
  background: rgba(255, 255, 255, 0.94);
}

.history-drawer-delete-btn {
  width: 100%;
  height: 80rpx;
  border-radius: 24rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, @coach-purple-700 0%, @coach-accent 100%);
  box-shadow: 0 2rpx 12rpx rgba(124, 92, 191, 0.35);
}

.history-drawer-delete-btn:active {
  opacity: 0.9;
}

.history-drawer-delete-text {
  font-size: 28rpx;
  color: #fff;
  font-weight: 500;
}

.history-drawer-footer-btns {
  display: flex;
  flex-direction: row;
  gap: 20rpx;
}

.history-drawer-btn-cancel,
.history-drawer-btn-confirm {
  flex: 1;
  height: 80rpx;
  border-radius: 24rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28rpx;
}

.history-drawer-btn-cancel {
  border: 2rpx solid rgba(124, 92, 191, 0.45);
  color: @coach-purple-700;
  background: rgba(255, 255, 255, 0.95);
}

.history-drawer-btn-confirm {
  background: @coach-purple-700;
  color: #fff;
  font-weight: 500;
}

.history-drawer-btn-confirm:active {
  opacity: 0.92;
}

.mas-top-actions {
  position: fixed;
  left: 0;
  right: 0;
  z-index: 99;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 10rpx 32rpx;
  background-color: rgba(250, 246, 255, 0.96);
  border-bottom: 1rpx solid rgba(124, 92, 191, 0.12);
  box-sizing: border-box;
  width: 100%;
  
  .action-btn-box {
    min-height: 40rpx;
    padding: 10rpx 28rpx;
    display: flex;
    justify-content: center;
    align-items: center;
    border: 1rpx solid rgba(124, 92, 191, 0.18);
    border-radius: 16rpx;
    /* 与首页 Goal Guardian 卡片主色一致 */
    background: linear-gradient(135deg, @coach-purple-500 0%, @coach-purple-700 100%);
    box-shadow: 0 8rpx 20rpx rgba(92, 61, 158, 0.18);
    transition: all 0.2s;
    
    &:active {
      opacity: 0.92;
    }
    
    .action-btn-text {
      font-size: 26rpx;
      font-weight: 500;
      color: #ffffff;
    }
  }
}

.chat-bottom-container {
  background-color: rgba(250, 246, 255, 0.98);
  box-sizing: border-box;
  width: 100%;
  position: fixed;
  margin: 0 auto;
  bottom: 0;
  /* 与原先一致：安全区一半 + 输入区内下边距，底栏整体离屏幕底更远 */
  padding-bottom: calc(env(safe-area-inset-bottom) / 2);
  /* 整块底栏顶部分割线（键盘/语音模式一致） */
  border-top: 1rpx solid rgba(124, 92, 191, 0.14);
  box-shadow: 0 -12rpx 32rpx rgba(92, 61, 158, 0.08);

  .input-bottom-container {
    width: 100%;
    /* 40+输入行+40，与上下 padding 一致 */
    min-height: 160rpx;
    box-sizing: border-box;
    /* 分割线→输入行、输入行→白底内底边 同为 40rpx；下边距与安全区不变，输入到屏幕底间距保持 */
    padding: 40rpx 6rpx 40rpx;
    display: flex;
    gap: 10rpx;
    /* 底边与输入框、发送按钮对齐；话筒在固定高度内垂直居中，避免偏上/偏下 */
    align-items: flex-end;

    .voice-icon-box {
      flex-shrink: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      width: 64rpx;
      height: 80rpx;
      box-sizing: border-box;
      .voice-icon {
        width: 32rpx;
        height: 42rpx;
        /* 与主色 #6236FF 对齐的紫色调 */
        filter: brightness(0) saturate(100%) invert(42%) sepia(58%) saturate(1800%)
          hue-rotate(232deg) brightness(96%) contrast(96%);
      }
    }

    .play-record-icon-box {
      flex-shrink: 0;
      padding: 8rpx;
      .play-record-icon {
        width: 32rpx;
        height: 40rpx;
        opacity: 0.85;
      }
    }

    .send-icon-box {
      width: 64rpx;
      height: 80rpx;
      flex-shrink: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      background-color: transparent;

      &.active .send-icon {
        /* 与语音键一致的主色 #6236FF，只改图标不着底 */
        filter: brightness(0) saturate(100%) invert(42%) sepia(58%) saturate(1800%)
          hue-rotate(232deg) brightness(96%) contrast(96%);
      }

      .send-icon {
        width: 32rpx;
        height: 32rpx;
      }
    }

    .input-box {
      flex: 1;
      min-width: 0;
      min-height: 80rpx;
      max-height: 300rpx;

      .textarea {
        width: 100%;
        min-height: 80rpx;
        max-height: 300rpx;
        padding: 20rpx 18rpx;
        box-sizing: border-box;
        background-color: rgba(255, 255, 255, 0.96);
        border: 1rpx solid rgba(124, 92, 191, 0.14);
        border-radius: 24rpx;
        font-size: 28rpx;
        color: @coach-purple-900;
        line-height: 1.5;
        word-wrap: break-word;
        white-space: pre-wrap;
        overflow-x: hidden;
        overflow-y: auto;
        /* 隐藏滚动条，保留滚动 */
        scrollbar-width: none;
        -ms-overflow-style: none;
        &::-webkit-scrollbar {
          display: none;
        }
      }
    }
  }

  .speech-box {
    padding-top: 32rpx;

    .voice-mode-textarea-wrap {
      margin-top: 24rpx;
      padding: 0 24rpx 24rpx;
      .voice-mode-textarea {
        width: 100%;
        min-height: 80rpx;
        max-height: 200rpx;
        padding: 20rpx 30rpx;
        box-sizing: border-box;
        background-color: rgba(255, 255, 255, 0.96);
        border: 1rpx solid rgba(124, 92, 191, 0.14);
        border-radius: 24rpx;
        font-size: 28rpx;
        color: @coach-purple-900;
        line-height: 1.5;
        word-wrap: break-word;
        white-space: pre-wrap;
        overflow-x: hidden;
        overflow-y: auto;
        scrollbar-width: none;
        -ms-overflow-style: none;
        &::-webkit-scrollbar {
          display: none;
        }
      }
    }
  }

  .recorder-box {

    .keybord-icon,
    .input-type-switch-btn {
      width: 96rpx;
      height: 96rpx;

      &.up {
        transform: rotate(180deg);
      }
    }
  }
}
</style>
