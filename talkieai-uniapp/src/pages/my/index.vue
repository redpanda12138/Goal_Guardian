<template>
	<view class="my-container">
		<CommonHeader class="header" title="Talkie" backgroundColor="#ffffff">
			<template v-slot:content>
				<text class="page-title">My Center</text>
			</template>
		</CommonHeader>
		<view class="mine-content">
			<!-- profile -->
			<view class="profile-box">
				<view v-if="accountInfo.account_id.indexOf('visitor') === 0" class="profile" @tap="hangleLogin">
					<image class="profile-avatar" src="/static/default-account-avatar.png" />
					<text class="profile-name">Please log in</text>
				</view>
				<view v-else class="profile">
					<image class="profile-avatar" src="/static/default-account-avatar.png" />
					<text class="profile-name">{{ displayUsername }}</text>
				</view>
			</view>
			<view class="mine-message-box">
				<view class="mine-list-box">
					<view class="mine-list-item">
						<text class="mine-list-item-title">Today notes number</text>
						<view><text class="mine-list-item-num">{{ accountInfo.today_chat_count }}</text></view>
					</view>
					<view class="mine-list-item">
						<text class="mine-list-item-title mine-list-item-title-total">Total notes number</text>
						<view><text class="mine-list-item-num">{{ accountInfo.total_chat_count }}</text></view>
					</view>
				</view>
			</view>
			<view class="setting">
				<view class="setting-card" @tap="goSchedule" v-if="accountInfo.account_id.indexOf('visitor') < 0">
					<uni-icons class="setting-card-logo" type="calendar" size="24" color="#7c5cbf" />
					<text class="setting-card-title">Schedule coaching</text>
				</view>
				<view class="setting-card" @tap="goFeedback">
					<uni-icons class="setting-card-logo" type="chatboxes-filled" size="24" color="#7c5cbf" />
					<text class="setting-card-title">Feedback</text>
				</view>
				<view class="setting-card" @tap="goContact">
					<uni-icons class="setting-card-logo" type="contact-filled" size="24" color="#7c5cbf" />
					<text class="setting-card-title">Contact us</text>
				</view>
				<view class="setting-card" @tap="goGithub">
					<uni-icons class="setting-card-logo" type="mail-open-filled" size="24" color="#7c5cbf" />
					<text class="setting-card-title">Github</text>
				</view>
				<!-- 如果是小程序登录 -->
				<view v-if="accountInfo.account_id.indexOf('visitor') < 0" class="logout-box" @tap="hangleLogout">
					<!-- <image class="setting-card-logo" src="/static/default-account-avatar.png" /> -->
					<text class="setting-card-title logout-text">Log out</text>
				</view>
			</view>
		</view>
	</view>
</template>

<script setup lang="ts">
import CommonHeader from "@/components/CommonHeader.vue";
import { ref, onMounted, computed } from "vue";

import accountRequest from '@/api/account';
import type { AccountInfo } from '@/models/models';
import {  onShow } from "@dcloudio/uni-app";


const accountInfo = ref<AccountInfo>({ account_id: '', patient_id: '', today_chat_count: 0, total_chat_count: 0, target_language_label: '' });
const displayUsername = computed(() => accountInfo.value.username || accountInfo.value.account_id);

onMounted(() => {
	uni.setNavigationBarTitle({
		title: 'TalkieAI'
	});
});

onShow(() => {
	accountRequest.accountInfoGet().then((data) => {
		accountInfo.value = data.data;
	});
});

const goContact = () => {
	uni.navigateTo({
		url: '/pages/contact/index'
	})
}

const goGithub = () => {
	const redirectUrl = 'https://github.com/IvaBojic/GoalGuardian';
	// #ifdef H5
	window.open(redirectUrl);
	// #endif

	// 非h5的情况提示用户访�?chatgpt-talkieai
	// #ifndef H5
	uni.showToast({
		title: '可通过github访问 chatgpt-talkieai',
		icon: 'none'
	})
	// #endif
}

const hangleLogout = () => {
	uni.showModal({
		title: 'Note',
		content: 'Are you sure to log out?',
		confirmText: 'Confirm',     // 添加这行 - 确认按钮文字
		cancelText: 'Cancel',  
		confirmColor: '#7c5cbf',
		success: function (res) {
			if (res.confirm) {
				uni.removeStorageSync('x-token');
				uni.reLaunch({
					url: '/pages/login/index'
				})
			} else if (res.cancel) {
				console.log('Cancel');
			}
		}
	});
}

const hangleLogin = () => {
	uni.removeStorageSync('x-token');
	uni.reLaunch({
		url: '/pages/login/index'
	})
}

const goFeedback = () => {
	uni.navigateTo({
		url: '/pages/feedback/index'
	})
}

const goSchedule = () => {
	uni.navigateTo({
		url: '/pages/my/schedule'
	});
}
</script>
<style scoped lang="less">
@import url('@/less/global.less');
@import url('@/less/coach-purple.less');

.page-title {
  display: inline-block;
  font-size: 38rpx;
  font-weight: 500;
  color: #333;
  position: relative;
  top: 8rpx;
}

.my-container {
	background: #ffffff;
	min-height: 100vh;
}

.mine-content {
	padding-bottom: 48rpx;
	padding-top: 16rpx;
	background: transparent;

	.profile-box {
		height: 176rpx;
		background: @coach-purple-500;
		box-shadow: 0 12rpx 36rpx rgba(92, 61, 158, 0.28);
		border-radius: 30rpx;
		padding: 36rpx;
		margin: 10rpx 32rpx;

		.profile {
			display: flex;
			align-items: center;

			.profile-avatar {
				width: 100rpx;
				height: 100rpx;
				border-radius: 24rpx;
			}

			.profile-name {
				margin-left: 40rpx;
				height: 40rpx;
				font-size: 38rpx;
				font-weight: 500;
				color: #ffffff;
				line-height: 40rpx;
			}
		}

	}

	.setting {
		margin-top: 15rpx;
		margin-left: 24rpx;
		margin-right: 24rpx;
		border-radius: 24rpx;
		overflow: hidden;
		background: #fff;
		box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.06);

		.setting-card {
			height: 100rpx;
			background: #fff;
			background-image: none;
			padding: 0 28rpx;
			display: flex;
			align-items: center;
			border-bottom: 1px solid #E8E8E8;
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
				display: flex;
				align-items: center;
				justify-content: center;
				flex-shrink: 0;
			}

			.setting-card-icon {
				width: auto;
				height: auto;
				display: flex;
				align-items: center;
			}

			.setting-card-title {
				flex: 1;
				font-size: 26rpx;
				line-height: 36rpx;
			}
		}

		.setting-card:nth-last-child(2) {
			border-bottom: none;
		}

		.logout-box {
			border-bottom: none;
		}

		.setting-card:active {
			background-color: #ffffff;
		}
	}

	.mine-message-box {
		padding: 10rpx 40rpx 0;

		.logo {
			width: 100%;
			height: 240rpx;
		}

		.mine-list-box {
			display: flex;
			padding-bottom: 40rpx;

			.mine-list-item {
				background: #fff;
				height: 220rpx;
				border-radius: 30rpx;
				width: 50%;
				padding: 38rpx;
				box-shadow: 0 4rpx 20rpx rgba(124, 92, 191, 0.06);
			}

			.mine-list-item:nth-child(2n) {
				margin-left: 32rpx;
			}

			.mine-list-item-title {
				font-size: 28rpx;
				color: #000;
				padding-left: 24rpx;
				position: relative;

			}

			.mine-list-item-title::after {
				position: absolute;
				content: '';
				width: 10rpx;
				height: 28rpx;
				border-radius: 5rpx;
				left: 0;
				top: 4rpx;
				background: @coach-purple-500;
			}

			.mine-list-item-title-total::after {
				background: #FF6B6B;
			}

			.mine-list-item-num {
				font-size: 64rpx;
				color: #000;
				font-weight: 500;
			}
		}
	}

	.subscribe-box {
		border-radius: 30rpx;
		margin: 0 32rpx;
		height: 200rpx;
		background: linear-gradient(180deg, #F6E6C5 0%, #EAC993 100%);
		box-shadow: 0rpx 0rpx 8rpx 0rpx rgba(196, 196, 196, 0.5);
		border-radius: 30rpx;
		padding: 40rpx 32rpx;

		.title-box {
			display: flex;
			align-items: center;

			.vip-icon-box {
				display: flex;
				align-items: center;

				.vip-icon {
					width: 80rpx;
					height: 53rpx;
				}

				.vip-text-icon {
					margin-left: 20rpx;
					width: 104rpx;
					height: 44rpx;
				}
			}

			.title {
				margin-left: 36rpx;
				font-size: 28rpx;
				color: #59370D;
			}
		}

		.btn-box {
			margin-top: 24rpx;
			width: 100%;
			display: flex;
			justify-content: center;

			.btn {
				width: 360rpx;
				height: 60rpx;
				background: #59370D;
				border-radius: 46rpx;
				display: flex;
				align-items: center;
				justify-content: center;

				.btn-text {
					font-weight: 400;
					color: #fff;
					line-height: 40rpx;
					height: 40rpx;
					font-size: 28rpx;
				}
			}
		}

		.vip-info-box {
			display: flex;
			align-items: baseline;
			justify-content: space-between;

			.btn-text {
				height: 40rpx;
				font-size: 28rpx;
				font-weight: 400;
				color: #000000;
				line-height: 40rpx;
			}

			.btn-box {
				padding: 10rpx 0;
				width: 138rpx;
				background: #59370D;
				border-radius: 58rpx;
				color: #fff;
				display: flex;
				justify-items: center;
				align-items: center;
			}
		}

		.left-box {
			flex: 1;

			.subscribe-title {
				font-size: 36rpx;
			}

			.subscribe-sub-title {
				margin-top: 12rpx;
				font-size: 24rpx;
			}
		}

		.right-box {
			width: 80rpx;
		}
	}
}

.logout-box {
	display: flex;
	justify-content: center;
	align-items: center;
	background: #fff;
	height: 100rpx;
	padding: 0 28rpx;
}

.logout-text {
	color: #707070;
}
</style>
