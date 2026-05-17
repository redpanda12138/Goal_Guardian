<template>
  <view class="container">
    <image class="logo" src="/static/logo.png"></image>
    <text class="title">
      Goal Guardian
    </text>
    <text class="sub-title">
      A health coaching for achieving health-related goals
    </text>
    
    <view class="input-box">
      <view style="padding-right: 10rpx"><text>Username:</text></view>
      <input 
        class="textarea" 
        confirm-type="next" 
        style="padding-left: 30rpx" 
        v-model="loginForm.username" 
        placeholder="" />
    </view>
    
    <view class="input-box">
      <view style="padding-right: 10rpx"><text>Password: </text></view>
      <input 
        class="textarea" 
        password 
        confirm-type="send" 
        @confirm="handleLogin"
        style="padding-left: 30rpx" 
        v-model="loginForm.password" 
        placeholder="" />
    </view>
    
    <button class="login-btn" @tap="handleLogin" :loading="loginLoading">
		{{ isRegisterMode ? 'Register' : 'Login' }}
	</button>
    
    <view class="register-link" @tap="switchToRegister" v-if="!isRegisterMode">
      Not our user? Register now
    </view>
    
    <view class="register-link" @tap="switchToLogin" v-else>
      Our user? Login now
    </view>
    
    <view class="divider">
      <text>or</text>
    </view>
    
    <text class="visitor-login" @tap="handleVisitorLogin()">Visitor Mode</text>
  </view>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import accountRequest from '@/api/account';
import Fingerprint2 from 'fingerprintjs2';

const X_TOKEN = 'x-token';
const loginLoading = ref(false);
const isRegisterMode = ref(false);

const loginForm = reactive({
  username: '',
  password: ''
});

onMounted(() => {
  uni.setNavigationBarTitle({
    title: 'Talkie'
  });
  
  // 检查是否已有保存的token
  let storageToken = uni.getStorageSync(X_TOKEN);
  if (storageToken) {
    loginSuccessByToken(storageToken);
  }
});

const switchToRegister = () => {
  isRegisterMode.value = true;
  resetForm();
};

const switchToLogin = () => {
  isRegisterMode.value = false;
  resetForm();
};

const resetForm = () => {
  loginForm.username = '';
  loginForm.password = '';
};

const handleLogin = () => {
  if (loginLoading.value) {
    return;
  }
  
  if (!loginForm.username.trim()) {
    uni.showToast({
      title: 'Please input username',
      icon: 'none'
    });
    return;
  }
  
  if (!loginForm.password.trim()) {
    uni.showToast({
      title: 'Please input password',
      icon: 'none'
    });
    return;
  }
  
  loginLoading.value = true;
  
  if (isRegisterMode.value) {
    // 注册逻辑
    accountRequest.register(loginForm)
      .then(data => {
        loginSuccess(data);
      })
      .catch(err => {
        uni.showToast({
          title: err.message || 'Fail to register',
          icon: 'none'
        });
      })
      .finally(() => {
        loginLoading.value = false;
      });
  } else {
    // 登录逻辑
    accountRequest.login(loginForm)
      .then(data => {
        loginSuccess(data);
      })
      .catch(err => {
        uni.showToast({
          title: err.message || 'Fail to login',
          icon: 'none'
        });
      })
      .finally(() => {
        loginLoading.value = false;
      });
  }
};

const handleVisitorLogin = () => {
  if (loginLoading.value) {
    return;
  }
  
  loginLoading.value = true;
  Fingerprint2.get((components) => {
    const values = components.map(component => component.value);
    const fingerprint = Fingerprint2.x64hash128(values.join(''), 31);
    
    accountRequest.visitorLogin({
      fingerprint: fingerprint
    })
      .then(data => {
        loginSuccess(data);
      })
	  .catch(err => {
	    uni.showToast({
	    title: err?.message || 'Visitor login failed',
	    icon: 'none'
	    });
	  })
      .finally(() => {
        loginLoading.value = false;
      });
  });
};

/**
 * 用户登录请求结果处理
 */
const loginSuccess = (data: any) => {
  if (data.code !== '200') {
    uni.showToast({
      title: data.message,
      icon: 'none'
    });
    return;
  }
  
  let storageToken = data.data;
  loginSuccessByToken(storageToken);
};

/**
 * 通过用户token加载后续逻辑
 */
const loginSuccessByToken = (storageToken: string) => {
  uni.setStorageSync('x-token', storageToken);
  uni.switchTab({
    url: '/pages/index/index'
  });
};
</script>

<style scoped lang="less">
@import url('@/less/coach-purple.less');

.container {
  min-height: 100vh;
  background: @coach-purple-surface;
  padding: 20vh 48rpx 0 48rpx;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  align-items: center;

  .logo {
    width: 120rpx;
    height: 120rpx;
  }

  .title {
    margin-top: 60rpx;
    width: 380rpx;
    height: 67rpx;
    font-size: 48rpx;
    font-weight: 600;
    color: #000000;
    line-height: 67rpx;
    letter-spacing: 1px;
  }

  .sub-title {
    margin-top: 20rpx;
    margin-bottom: 80rpx;
    width: 550rpx;
    height: 45rpx;
    font-size: 32rpx;
    color: #939193;
    line-height: 45rpx;
    letter-spacing: 1px;
    text-align: center;
  }

  .input-box {
    margin-top: 30rpx;
    display: flex;
    flex-direction: row;
    height: 60rpx;
    color: #939193;
    width: 550rpx;

    .textarea {
      flex: 1;
      background-color: rgba(241, 241, 243, 1);
      box-sizing: border-box;
      border-radius: 40px;
      height: 100%;
      padding: 0 30rpx;
    }
  }

  .login-btn {
    width: 500rpx;
    height: 90rpx;
    border-radius: 24rpx;
    background-color: @coach-purple-500;
    color: #fff;
    font-size: 32rpx;
    font-weight: 400;
    margin-top: 40rpx;
  }

  .register-link {
    margin-top: 30rpx;
    height: 45rpx;
    font-size: 28rpx;
    font-weight: 400;
    color: @coach-purple-500;
    line-height: 45rpx;
    letter-spacing: 1px;
    text-decoration: underline;
  }

  .divider {
    width: 100%;
    text-align: center;
    position: relative;
    margin: 60rpx 0;
    color: #939193;
  }

  .divider::before {
    content: "";
    position: absolute;
    left: 0;
    top: 50%;
    width: 100%;
    height: 1px;
    background-color: #E8E8E8;
    z-index: 1;
  }

  .divider text {
    position: relative;
    z-index: 2;
    background-color: #fff;
    padding: 0 20rpx;
  }

  .visitor-login {
    height: 45rpx;
    font-size: 28rpx;
    font-weight: 400;
    color: #939193;
    line-height: 45rpx;
    letter-spacing: 1px;
  }
}
</style>
