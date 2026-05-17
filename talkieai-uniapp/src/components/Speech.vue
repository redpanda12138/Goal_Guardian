<template>
  <view class="speech-container">
    <!-- 未开始录音 -->
    <view v-if="!recorder.start && !recorder.completed" class="recorder-box">
      <slot name="leftMenu">
        <view></view>
      </slot>
      <view @tap="handleSpeech" class="recorder-btn-box">
        <view class="voice-circle">
          <image class="voice-icon" src="/static/icon_voice.png"></image>
        </view>
      </view>
      <slot name="rightMenu">
        <view></view>
      </slot>
    </view>

    <!-- 开始录音 -->
    <view v-if="recorder.start" @tap="handleSpeechEnd" class="recordering-box">
      <view class="outter-circle animated"></view>
      <view class="recordering-circle">
        <view class="recordering-square"></view>
      </view>
    </view>

    <!-- 录音结束 -->
    <view v-if="recorder.completed" class="recorder-completed-box">
      <view @tap="handleTrash" class="trash-btn-box">
        <image class="trash-btn" src="/static/icon_trash.png"></image>
      </view>
      <view @tap="handlePlaySpeech" class="play-btn-box">
        <image
          v-if="!voicePlaying"
          class="play-btn"
          src="/static/icon_menu_play.png"
        >
        </image>
        <image
          v-else="voicePlaying"
          class="play-btn"
          style="width: 100%; height: 100%"
          src="/static/menu_voice_playing.gif"
        ></image>
      </view>
      <view @tap="handleSend" class="send-btn-box">
        <LoadingRound v-if="recorder.processing"></LoadingRound>
        <image
          v-if="!recorder.processing"
          class="send-btn"
          src="/static/icon_send.png"
        ></image>
      </view>
    </view>
  </view>
</template>
<script setup lang="ts">
import { ref, defineEmits, getCurrentInstance } from "vue";
import LoadingRound from "@/components/LoadingRound.vue";
import speech from "./speechExecuter";
// import audioPlayer from "@/components/audioPlayerExecuter";
import audioPlayer from "./audioPlayerExecuter"; // 导入共享对象
import utils from "@/utils/utils";

const emit = defineEmits();

const $bus: any = getCurrentInstance()?.appContext.config.globalProperties.$bus;
const recorder = ref({
  start: false,
  processing: false,
  completed: false,
  voiceFileName: null,
});
const voicePlaying = ref(false);

/**
 * 开始录音
 */
const handleSpeech = () => {
  if (recorder.value.start) {
    speech.handleEndVoice();
    return;
  }

  audioPlayer.stopAudio();
  recorder.value.start = true;
  recorder.value.completed = false;
  speech.handleVoiceStart({
    processing: () => {
      recorder.value.processing = true;
    },
    success: ({ voiceFileName }) => {
      recorder.value.voiceFileName = voiceFileName;
      recorder.value.processing = false;
      recorder.value.start = false;
      recorder.value.completed = true;
      emit("completed", { fileName: voiceFileName });
    },
    interval: (interval: any) => {
      recorder.value.remainingTime = interval;
    },
    cancel: () => {
      recorder.value.processing = false;
      recorder.value.start = false;
    },
    error: (err: any) => {
      recorder.value.processing = false;
      recorder.value.start = false;
    },
  });
};

/**
 * 结束录音
 */
const handleSpeechEnd = () => {
  speech.handleEndVoice();
};

/**
 * 删除录音
 */
const handleTrash = () => {
  emit("delete");
  recorder.value.completed = false;
};

/**
 * 播放录音
 */
const handlePlaySpeech = () => {
  if (!recorder.value.voiceFileName) {
    console.error("没有语音文件");
    return;
  }
  audioPlayer.playAudio({
    audioUrl: utils.getVoiceFileUrl(recorder.value.voiceFileName),
    listener: {
      playing: () => {
        voicePlaying.value = true;
      },
      success: () => {
        voicePlaying.value = false;
        console.log(voicePlaying.value);
      },
      error: () => {
        voicePlaying.value = false;
      },
    },
  });
};

/**
 * 发送：由父组件根据下方文字栏内容发送文字
 */
const handleSend = () => {
  if (!recorder.value.voiceFileName) {
    console.error("没有语音文件");
    return;
  }
  emit("send", { fileName: recorder.value.voiceFileName });
  recorder.value.completed = false;
};
</script>
<style lang="scss" scoped>
@import "@/less/coach-purple.scss";

.speech-container {
  min-height: 125rpx;
  height: 236rpx;
}

.recorder-btn-box,
.play-btn-box {
  margin: 0 100rpx;
}

.recorder-completed-box,
.recorder-box {
  padding: 24rpx 90rpx 0 90rpx;
  display: flex;
  // gap: 100rpx;
  box-sizing: border-box;
  width: 100%;
  align-items: center;
  justify-content: center;
}

.recorder-completed-box {
  .recorder-btn-box {
    width: 176rpx;
    height: 176rpx;
    background-color: rgba(232, 224, 244, 0.96);
    border-radius: 87px;
    padding: 20rpx;
    box-sizing: border-box;
    border: 1rpx solid rgba(124, 92, 191, 0.14);
  }

  .trash-btn-box {
    min-width: 96rpx;
    height: 96rpx;
    border-radius: 48rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: rgba(255, 255, 255, 0.96);
    border: 1rpx solid rgba(124, 92, 191, 0.16);
    box-shadow: 0 8rpx 18rpx rgba(92, 61, 158, 0.06);

    .trash-btn {
      width: 32rpx;
      height: 32rpx;
      filter: brightness(0) saturate(100%) invert(37%) sepia(18%) saturate(1238%)
        hue-rotate(226deg) brightness(94%) contrast(90%);
    }
  }

  .play-btn-box {
    min-width: 136rpx;
    height: 136rpx;
    border-radius: 88rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, $coach-purple-500 0%, $coach-purple-700 100%);
    box-shadow: 0 12rpx 28rpx rgba(92, 61, 158, 0.2);

    .play-btn {
      width: 32rpx;
      height: 48rpx;
    }
  }

  .send-btn-box {
    min-width: 96rpx;
    height: 96rpx;
    border-radius: 48rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, $coach-purple-500 0%, $coach-purple-700 100%);
    box-shadow: 0 12rpx 28rpx rgba(92, 61, 158, 0.2);
    &.translating {
      background: rgba(209, 196, 233, 0.9);
      box-shadow: none;
    }

    .send-btn {
      width: 32rpx;
      height: 32rpx;
    }
  }
}

.recorder-completed-box {
  padding: 40rpx 20rpx 0 20rpx;
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

  .recorder-btn-box {
    width: 176rpx;
    height: 176rpx;
    background-color: rgba(232, 224, 244, 0.96);
    border-radius: 87px;
    padding: 20rpx;
    box-sizing: border-box;
    border: 1rpx solid rgba(124, 92, 191, 0.14);
    box-shadow: 0 14rpx 32rpx rgba(92, 61, 158, 0.12);

    .voice-circle {
      width: 136rpx;
      height: 136rpx;
      background: linear-gradient(135deg, $coach-purple-500 0%, $coach-purple-700 100%);
      border-radius: 70px;
      padding: 44rpx 50rpx 44rpx 50rpx;
      box-sizing: border-box;
      box-shadow: inset 0 -6rpx 12rpx rgba(61, 42, 92, 0.14);

      .voice-icon {
        width: 36rpx;
        height: 48rpx;
      }
    }
  }
}

.recordering-box {
  display: flex;
  position: relative;
  padding: 24rpx 90rpx 0 90rpx;
  justify-content: center;
  align-items: center;

  .outter-circle.animated {
    width: 176rpx;
    height: 176rpx;
    background-color: rgba(156, 128, 207, 0.26);
    position: relative;
    border-radius: 50%;
    animation: scale-40df7b08 2s infinite;

    @keyframes scale-40df7b08 {
      0% {
        transform: scale(1);
        opacity: 1;
      }

      50% {
        transform: scale(0.8);
        opacity: 0.9;
      }

      to {
        transform: scale(1);
        opacity: 1;
      }
    }
  }

  .recordering-circle {
    position: absolute;
    background: linear-gradient(135deg, $coach-purple-500 0%, $coach-purple-700 100%);
    border-radius: 70px;
    padding: 44rpx 44rpx 44rpx 44rpx;
    box-sizing: border-box;
    box-shadow: 0 12rpx 28rpx rgba(92, 61, 158, 0.24);

    .recordering-square {
      position: relative;
      background-color: rgba(255, 255, 255, 1);
      border-radius: 6px;
      width: 48rpx;
      height: 48rpx;
      box-sizing: border-box;
    }
  }
}
</style>
