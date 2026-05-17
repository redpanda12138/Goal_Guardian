<template>
  <view class="settings-page">
    <CommonHeader :leftIcon="true" :back-fn="handleBackPage" title="Talkie">
      <template v-slot:content>
        <text class="settings-title">Settings</text>
      </template>
    </CommonHeader>
    <view class="mine-content">
      <view class="setting">
        <view class="setting-card">
          <text class="setting-card-title">Auto-play audio</text>
          <Checkbox
            @input="(check) => inputCheck('auto_playing_voice', check)"
            :checked="settingInfo.auto_playing_voice === 1"
          />
        </view>
        <view class="setting-card">
          <text class="setting-card-title">Auto-blur text</text>
          <Checkbox
            @input="(check) => inputCheck('auto_text_shadow', check)"
            :checked="settingInfo.auto_text_shadow === 1"
          />
        </view>
        <view class="setting-card">
          <text class="setting-card-title">Auto pronunciation scoring</text>
          <Checkbox
            @input="(check) => inputCheck('auto_pronunciation', check)"
            :checked="settingInfo.auto_pronunciation === 1"
          />
        </view>
      </view>
      <view class="setting-bot">
        <text class="setting-card-title">Playback speed</text>
        <view class="tab-box">
          <view :class="`tab-item ${settingInfo.playing_voice_speed == '0.5' ? 'tab-item-select' : ''}`" @tap="selectTab('0.5')">
            <text>Slow</text>
          </view>
          <view :class="`tab-item ${settingInfo.playing_voice_speed == '1.0' ? 'tab-item-select' : ''}`" @tap="selectTab('1.0')">
            <text>Normal</text>
          </view>
          <view :class="`tab-item ${settingInfo.playing_voice_speed == '1.5' ? 'tab-item-select' : ''}`" @tap="selectTab('1.5')">
            <text>Fast</text>
          </view>
        </view>
        <button @tap="deleteLatestMessages" class="common-button setting-clear-latest">
          Clear last chat
        </button>
        <button @tap="deleteAllMessages" class="common-button setting-clear">
          Clear all chats
        </button>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import CommonHeader from "@/components/CommonHeader.vue";
import Checkbox from "@/components/Checkbox.vue";
import { ref } from "vue";
import { onShow, onLoad } from "@dcloudio/uni-app";
import accountRequest from "@/api/account";
import chatRequest from "@/api/chat";

const settingInfo = ref<any>({});
const sessionId = ref<string>("");

onLoad((options: any) => {
  uni.setNavigationBarTitle({
    title: "Talkie",
  });
  sessionId.value = options.sessionId;
});

onShow(() => {
  accountRequest.getSettings().then((data) => {
    if (data.code === "200") {
      settingInfo.value = data.data;
    }
  });
});

const handleBackPage = () => {
  const pages = getCurrentPages();
  if (pages.length > 1) {
    uni.navigateBack({
      delta: 1,
      fail: () => {
        uni.switchTab({
          url: "/pages/index/index",
        });
      },
    });
  } else {
    uni.switchTab({
      url: "/pages/index/index",
    });
  }
};

const selectTab = (id: string) => {
  settingInfo.value.playing_voice_speed = id;
  accountRequest
    .setSettings({
      playing_voice_speed: id,
    })
    .then((data) => {
      console.log(data);
      if (data.code === "200") {
        console.log("Settings updated");
      }
    });
};

const inputCheck = (type: string, check: boolean) => {
  accountRequest
    .setSettings({
      [type]: check ? 1 : 0,
    })
    .then((data) => {
      console.log(data);
      if (data.code === "200") {
        console.log("Settings updated");
      }
    });
};

const deleteLatestMessages = () => {
  uni.showModal({
    title: "Confirm",
    content: "Are you sure you want to clear the last chat?",
    success: function (res) {
      if (res.confirm) {
        console.log("Confirmed");
        chatRequest.messagesLatestDelete(sessionId.value).then((data) => {
          console.log(data);
          uni.showToast({
            title: "Cleared",
            icon: "none",
          });
          uni.navigateTo({
            url: `/pages/chat/index?sessionId=${sessionId.value}`,
          });
        });
      } else if (res.cancel) {
        console.log("Cancelled");
      }
    },
  });
};

const deleteAllMessages = () => {
  uni.showModal({
    title: "Confirm",
    content: "Are you sure you want to clear all chat history?",
    success: function (res) {
      if (res.confirm) {
        console.log("Confirmed");
        chatRequest.messagesAllDelete(sessionId.value).then((data) => {
          console.log(data);
          uni.showToast({
            title: "Cleared",
            icon: "none",
          });
          uni.navigateTo({
            url: `/pages/chat/index?sessionId=${sessionId.value}`,
          });
        });
      } else if (res.cancel) {
        console.log("Cancelled");
      }
    },
  });
};
</script>
<style scoped lang="less">
@import url("@/less/global.less");
@import url("@/less/coach-purple.less");

.settings-page {
  min-height: 100vh;
  background: @coach-purple-surface;
}

.settings-title {
  color: @coach-purple-900;
  font-weight: 600;
}

.common-switch {
  .uni-switch-input {
    border-color: #9b82c9;
    background-color: #9b82c9;
  }
}

.mine-content {
  background: @coach-purple-surface;
  min-height: calc(100vh - 100rpx);

  .setting {
    margin-top: 38rpx;
    margin-left: 24rpx;
    margin-right: 24rpx;
    border-radius: 24rpx;
    overflow: hidden;
    background: rgba(255, 255, 255, 0.95);
    border: 1rpx solid rgba(124, 92, 191, 0.12);
    box-shadow: 0 12rpx 28rpx rgba(92, 61, 158, 0.08);

    .setting-card {
      background: #fff;
      background-image: none;
      background-size: 16rpx 28rpx;
      border-bottom: 1px solid rgba(124, 92, 191, 0.12);
      padding: 50rpx 32rpx;
      display: flex;
      align-items: center;
      justify-content: space-between;
      list-style: none;

      &::after,
      &::before {
        content: none !important;
        display: none !important;
      }

      .setting-card-logo {
        width: 28rpx;
        height: 28rpx;
        margin-right: 20rpx;
      }

      .setting-card-title {
        color: @coach-purple-700;
        font-weight: 500;
        font-size: 30rpx;
      }

      text:last-child {
        color: #9b82c9;
        font-size: 28rpx;
      }
    }

    .setting-card:last-child {
      border-bottom: none;
    }
  }

  .setting-bot {
    padding: 36rpx;

    .setting-card-title {
      color: @coach-purple-700;
      font-weight: 500;
      font-size: 30rpx;
      display: block;
    }

    .setting-clear-latest {
      width: 100%;
      background: rgba(255, 255, 255, 0.96);
      border: 1rpx solid rgba(124, 92, 191, 0.12);
      border-radius: 30rpx;
      color: @coach-purple-700;
      font-size: 28rpx;
      margin-top: 150rpx;
      box-shadow: 0 10rpx 24rpx rgba(92, 61, 158, 0.08);
    }

    .setting-clear {
      width: 100%;
      background: rgba(255, 255, 255, 0.96);
      border: 1rpx solid rgba(124, 92, 191, 0.12);
      border-radius: 30rpx;
      color: @coach-purple-700;
      font-size: 28rpx;
      margin-top: 20rpx;
      box-shadow: 0 10rpx 24rpx rgba(92, 61, 158, 0.08);
    }

    .setting-clear::after {
      border: none;
    }
  }

  .tab-box {
    width: 100%;
    background: rgba(255, 255, 255, 0.96);
    border: 1rpx solid rgba(124, 92, 191, 0.12);
    border-radius: 30rpx;
    display: flex;
    flex: 1;
    padding: 10rpx;
    margin-top: 24rpx;
    box-shadow: 0 8rpx 20rpx rgba(92, 61, 158, 0.05);

    .tab-item {
      display: block;
      flex: 1;
      text-align: center;
      padding: 34rpx 0;
      transition: 0.3s all linear;
      color: #9b82c9;
      font-size: 28rpx;
    }

    .tab-item:active {
      opacity: 0.9;
    }

    .tab-item-select {
      background: @coach-purple-300;
      color: #fff;
      border-radius: 30rpx;
      font-weight: 500;
    }
  }
}
</style>
