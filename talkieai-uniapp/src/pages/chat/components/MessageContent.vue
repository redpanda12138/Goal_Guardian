<template>
  <view class="message-container" :class="containerClass">
    <!-- loading -->
    <view v-if="!message.content" class="loading-box">
      <Loading />
    </view>
    <!-- MAS 状态更新（不计入教练对话气泡） -->
    <view v-else-if="isStateEvent" class="state-event-strip">
      <text class="state-event-label">Status update</text>
      <text class="state-event-text">{{ stateEventContent }}</text>
    </view>
    <!-- 具体内容 -->
    <view v-else class="message-box">
      <view class="message-text-box" :class="{ 'own-text-box': message.owner }">
        <!-- AI消息 -->
        <view v-if="!message.owner" class="assistant-text-box">
          <FunctionalText ref="functionalTextRef" :auto-play="message.auto_play || false" :messageId="message.id"
            :wordClickable="true" :text="message.content" :fileName="message.file_name" :translateShow="translateShow"
         />
          <view class="divider"></view>
          <view class="action-container">
            <view class="btn-box" :class="{ active: translateShow }">
              <image class="action-icon" @tap="handleTranslateText" src="/static/icon_translate.png" />
            </view>
            <view class="btn-box collect-btn-box">
              <Collect type="MESSAGE" :messageId="message.id || ''" />
            </view>
            <view class="btn-box">
              <image class="action-icon" @tap="handleCopyText" src="/static/icon_copy_text.png" />
            </view>
          </view>
        </view>

        <!-- 用户消息 -->
        <view v-else class="account-text-container">
          <view class="account-text-box">

            <!-- 展示语音分析结果 -->
            <!-- <TextPronunciation v-if="message.pronunciation" :content="message.content" :pronunciation="message.pronunciation" @wordClick="handleWordDetail" />
            
            <view v-else>{{ message.content }}</view> -->
            <view>{{ message.content }}</view>

            <!-- 语音播放 -->
            <view v-if="message.file_name" class="speech-box">
              <AudioPlayer direction="right" :fileName="message.file_name" />
            </view>
          </view>
        </view>
      </view>

      <!-- 语法 -->
      <view v-if="message.owner && !isStateEvent" class="grammar-outter-box">
        <LoadingRound v-if="grammarLoading" class="grammar-box" />
        <view v-else-if="message.pronunciation" class="grammar-box" @tap="handleGrammar">
          <image class="grammar-icon" src="/static/icon_grammar.png" />
          <text class="grammar-score">{{ utils.removeDecimal(message.pronunciation.pronunciation_score) }}</text>
        </view>
        <view v-else class="grammar-box" @tap="handleGrammar">
          <image class="grammar-icon" src="/static/icon_grammar.png" />
          <text>Review</text>
        </view>
      </view>
    </view>
    <MessageGrammar ref="messageGrammarRef" />
  </view>
</template>
<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from "vue";
import FunctionalText from "@/components/FunctionalText.vue";
import AudioPlayer from "@/components/AudioPlayer.vue";
import MessageGrammar from "./MessageGrammarPopup.vue";
import Collect from "@/components/Collect.vue";
import type { Message, MessagePage, Session } from "@/models/models";
import Loading from "@/components/Loading.vue";
import LoadingRound from "@/components/LoadingRound.vue";
import chatRequest from "@/api/chat";
import utils from "@/utils/utils";

const functionalTextRef = ref(null);
const messageGrammarRef = ref(null);
const grammarLoading = ref(false);
const translateShow = ref(false);

const props = defineProps<{
  message: Message;
}>();

onMounted(() => {
  if (props.message.auto_pronunciation) {
    autoPronunciation();
  }
});

const ownerMessage = computed(() => {
  return props.message.owner;
});

const isStateEvent = computed(() => {
  const st = props.message.style || "";
  return (
    st.startsWith("STATE_EVENT:") ||
    props.message.message_kind === "state_event"
  );
});

const stateEventContent = computed(() => {
  const raw = props.message.content || "";
  if (!isStateEvent.value || !raw) {
    return raw;
  }

  return raw
    .replace(/^状态更新[:：]\s*目标\s*(\d+)\s*已标记为完成[。.]?$/u, "Status update: Goal $1 has been marked complete.")
    .replace(/^状态更新[:：]\s*/u, "Status update: ")
    .replace(/已标记为完成[。.]?$/u, "has been marked complete.");
});

const containerClass = computed(() => {
  if (isStateEvent.value) {
    return "center-content state-event-wrap";
  }
  const messagePosition = props.message.owner ? "right" : "left";
  return `${messagePosition}-content`;
});

const handleTranslateText = () => {
  translateShow.value = !translateShow.value;
};

const handleCopyText = () => {
  uni.setClipboardData({
    data: props.message.content,
    success: () => {
      uni.showToast({
        title: "Copied",
        icon: "none",
      });
    },
  });
};


const handleGrammar = () => {
  let type = "grammar";
  if (props.message.file_name) {
    type = "pronunciation";
  }
  messageGrammarRef.value.open(
    props.message.id,
    props.message.content,
    props.message.file_name,
    props.message.session_id,
    type
  );
};

/**
 * 用于显露到外面的方法，用于外部调用播放
 */
const autoPlayAudio = () => {
  nextTick(() => {
    functionalTextRef.value.autoPlayAudio();
  });
};

const autoPronunciation = () => {
  grammarLoading.value = true;
  chatRequest
    .pronunciationInvoke({ message_id: props.message.id })
    .then((data) => {
      // 更新message对象的pronunciation属性
      props.message.pronunciation = data.data;
      grammarLoading.value = false;
    });
};

/**
 * 用于显露到外面的方法，用于外部调用模糊
 */
const autoHandleHint = () => {
  handleHint();
};

defineExpose({
  autoPlayAudio,
  autoHandleHint,
  autoPronunciation,
});
</script>
<style lang="less" scoped>
.speech-box {
  display: flex;
  align-items: center;
  height: 22px;
}

.message-container {
  display: flex;
  flex-direction: column;

  .message-box {
    max-width: 80%;

    .message-text-box {
      padding: 28rpx 36rpx;
      border-radius: 8rpx 30rpx 30rpx;
      color: #333;
      display: flex;
      flex-direction: column;

      &.own-text-box {
        border-radius: 30rpx 8rpx 30rpx 30rpx;
      }
    }
  }

  .divider {
    margin: 14px 0 8px;
    width: 100%;
    height: 1px;
    background: rgba(0, 0, 0, 0.08);
  }

  &.right-content {
    align-items: flex-end;

    .message-text-box {
      background-color: rgba(232, 224, 244, 0.9);
      border: 1rpx solid rgba(124, 92, 191, 0.16);
    }

    .account-text-container {
      .account-text-box {
        display: flex;
        flex-direction: row-reverse;
        gap: 16rpx;
      }
    }

    .grammar-outter-box {
      display: flex;
      flex-direction: row-reverse;

      .grammar-box {
        margin-top: 12rpx;
        display: flex;
        border: 1rpx solid rgba(124, 92, 191, 0.26);
        padding: 12rpx 28rpx;
        align-items: center;
        border-radius: 10rpx;
        background: rgba(255, 255, 255, 0.9);

        .grammar-icon {
          width: 28rpx;
          height: 28rpx;
          margin-right: 14rpx;
        }

        .grammar-score {
          color: rgb(17, 165, 129);
        }
      }
    }
  }

  &.left-content {
    align-items: flex-start;

    .message-text-box {
      background-color: rgba(255, 255, 255, 0.96);
      border: 1rpx solid rgba(124, 92, 191, 0.12);
    }

    .action-container {
      display: flex;

      .btn-box {
        margin-left: 16rpx;
        height: 48rpx;
        width: 48rpx;
        display: flex;
        justify-content: center;
        align-items: center;

        &.active {
          background-color: #fff;
        }

        &:first-child {
          margin-left: 0;
        }
      }
    }

    .action-icon {
      width: 32rpx;
      height: 32rpx;
    }
  }

  &.center-content.state-event-wrap {
    align-items: center;
    width: 100%;
  }
}

.state-event-strip {
  width: 92%;
  max-width: 640rpx;
  padding: 16rpx 24rpx;
  border-radius: 12rpx;
  background: rgba(232, 224, 244, 0.72);
  border: 1rpx solid rgba(124, 92, 191, 0.2);
}

.state-event-label {
  display: block;
  font-size: 22rpx;
  color: #5c3d9e;
  margin-bottom: 8rpx;
}

.state-event-text {
  font-size: 26rpx;
  color: #4a3d6d;
  line-height: 1.4;
}
</style>
