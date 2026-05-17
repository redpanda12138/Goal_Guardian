<script setup lang="ts">
import { ref, computed } from 'vue';
import speech from './speechExecuter';
import audioPlayer from './audioPlayerExecuter';
import utils from '@/utils/utils';
import chatRequest from '@/api/chat'; // 引入chat API

const props = defineProps<{
  sessionId?: string;
  onTranscriptionComplete?: (text: string) => void;
  onRecordingComplete?: (file: string) => void;
}>(); 

const emit = defineEmits<{
  (e: 'transcriptionComplete', text: string): void;
  (e: 'recordingComplete', file: string): void;
  (e: 'error', error: Error): void;
  (e: 'close'): void;
}>();

const isRecording = ref(false);
const recordedFile = ref<string | null>(null);
const transcriptionResult = ref('');
const recordingTime = ref(0);
let timer: number | null = null;

// 格式化录音时间
const formattedTime = computed(() => {
  const minutes = Math.floor(recordingTime.value / 60);
  const seconds = recordingTime.value % 60;
  return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
});

// 切换录音状态
const toggleRecording = () => {
  if (isRecording.value) {
    stopRecording();
  } else {
    startRecording();
  }
};

// 开始录音
const startRecording = () => {
  isRecording.value = true;
  recordingTime.value = 0;
  
  // 开始计时
  timer = setInterval(() => {
    recordingTime.value++;
    // 最大录音时间限制为60秒
    if (recordingTime.value >= 60) {
      stopRecording();
    }
  }, 1000) as unknown as number;

  speech.handleVoiceStart({
    success: ({ voiceFileName }) => {
      recordedFile.value = voiceFileName;
      isRecording.value = false;
      transcriptionResult.value = '';
      
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
      
      // 自动发送语音到服务器进行转录
      transcribeVoice(voiceFileName);
    },
    cancel: () => {
      isRecording.value = false;
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
    },
    error: (err: Error) => {
      isRecording.value = false;
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
      
      // 检查是否为权限错误
      const errorMessage = err.message || String(err);
      if (errorMessage.toLowerCase().includes('permission') || errorMessage.includes('denied')) {
        uni.showModal({
          title: '麦克风权限被拒绝',
          content: '当前浏览器录音权限被拒绝，请在浏览器地址栏右侧的权限设置中允许麦克风访问，然后刷新页面重试。',
          showCancel: true,
          confirmText: '去设置',
          cancelText: '取消',
          success: (modalRes) => {
            if (modalRes.confirm) {
              // 尝试引导用户到设置页面，虽然无法直接打开设置，但可以提示用户操作步骤
              uni.showToast({
                title: '请手动在浏览器设置中开启麦克风权限',
                icon: 'none',
                duration: 3000
              });
            }
          }
        });
      } else {
        uni.showToast({
          title: `录音出错: ${err.message || '未知错误'}`,
          icon: 'none'
        });
      }
      emit('error', err);
    },
    interval: (remainingTime: number) => {
      // 这里可以处理剩余时间
    },
    processing: () => {
      // 处理上传中状态
    }
  });
};

// 停止录音
const stopRecording = () => {
  speech.handleEndVoice();
};

// 转录音频
const transcribeVoice = async (fileName: string) => {
  try {
    // 使用独立的语音转文字接口，不需要sessionId
    const response = await chatRequest.standaloneTransformText({
      file_name: fileName
    });
    
    transcriptionResult.value = response.data.transcribed_text || '';
    
    if (props.onTranscriptionComplete) {
      props.onTranscriptionComplete(transcriptionResult.value);
    }
    emit('transcriptionComplete', transcriptionResult.value);
  } catch (error) {
    console.error('语音转文字失败:', error);
    uni.showToast({
      title: '语音转文字失败',
      icon: 'none'
    });
    emit('error', error as Error);
  }
};

// 使用识别结果
const useTranscription = () => {
  if (transcriptionResult.value) {
    emit('transcriptionComplete', transcriptionResult.value);
  }
};

// 重试录音
const retryRecording = () => {
  recordedFile.value = null;
  transcriptionResult.value = '';
};

// 播放录音
const playRecording = () => {
  if (recordedFile.value) {
    audioPlayer.playAudio({
      audioUrl: utils.getVoiceFileUrl(recordedFile.value),
      listener: {
        playing: () => {
          console.log('Playing recording...');
        },
        success: () => {
          console.log('Playback finished.');
        },
        error: (err: any) => {
          console.error('Playback error:', err);
          uni.showToast({
            title: '播放失败',
            icon: 'none'
          });
        }
      }
    });
  }
};

// 删除录音
const deleteRecording = () => {
  recordedFile.value = null;
  transcriptionResult.value = '';
  isRecording.value = false;
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
};

// 关闭识别组件
const closeRecognition = () => {
  emit('close');
};

// 组件销毁时清理定时器
defineExpose({
  stopRecording,
  deleteRecording
});
</script>

<style lang="scss" scoped>
.voice-recognition-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 90%;
  max-width: 600rpx;
  background-color: #fff;
  border-radius: 20rpx;
  padding: 40rpx 20rpx;
  position: relative;
}

.recognition-header {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30rpx;
  padding-bottom: 20rpx;
  border-bottom: 1rpx solid #E8E8E8;
}

.header-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #333;
}

.close-btn {
  width: 50rpx;
  height: 50rpx;
  border-radius: 50%;
  background-color: #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32rpx;
  color: #707070;
  border: none;
}

.recording-button {
  width: 120rpx;
  height: 120rpx;
  border-radius: 50%;
  background-color: #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;

  &.recording {
    background-color: #ff6b6b;
    box-shadow: 0 0 30rpx rgba(255, 107, 107, 0.5);
  }
}

.mic-icon {
  width: 50rpx;
  height: 50rpx;
}

.recording-indicator {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.pulse-ring {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  border: 6rpx solid #ff6b6b;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% {
    transform: scale(1);
    opacity: 1;
  }
  75% {
    transform: scale(1.3);
    opacity: 0.3;
  }
  100% {
    transform: scale(1.3);
    opacity: 0;
  }
}

.recording-status {
  margin: 20rpx 0;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.recording-text {
  font-size: 28rpx;
  color: #707070;
  margin-bottom: 10rpx;
}

.timer {
  font-size: 24rpx;
  color: #999;
  font-weight: bold;
}

.transcription-result {
  margin: 30rpx 0;
  width: 100%;
  background-color: #f9f9f9;
  border-radius: 10rpx;
  padding: 20rpx;
  max-height: 200rpx;
  overflow-y: auto;
}

.result-text {
  display: block;
  font-size: 28rpx;
  color: #333;
  line-height: 1.5;
  margin-bottom: 20rpx;
  word-break: break-all;
}

.result-actions {
  display: flex;
  gap: 20rpx;
}

.action-btn {
  flex: 1;
  padding: 15rpx;
  border-radius: 8rpx;
  font-size: 26rpx;
  color: white;
  border: none;
}

.use-btn {
  background-color: #6236FF;
}

.retry-btn {
  background-color: #999;
}

.recording-controls {
  display: flex;
  gap: 30rpx;
  margin-top: 20rpx;
}

.control-btn {
  width: 60rpx;
  height: 60rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f0f0f0;
  border: none;
}

.play-btn {
  background-color: #6236FF;
}

.delete-btn {
  background-color: #ff6b6b;
}

.control-icon {
  width: 30rpx;
  height: 30rpx;
}

.instructions {
  margin-top: 30rpx;
  width: 100%;
}

.instruction-text {
  font-size: 24rpx;
  color: #999;
  text-align: center;
}
</style>