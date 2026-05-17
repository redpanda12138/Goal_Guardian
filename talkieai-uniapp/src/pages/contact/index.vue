<template>
	<view>
		<CommonHeader :leftIcon='true' :back-fn="handleBackPage" class="header" title="Talkie">
			<template v-slot:content>
				<text>Contact us</text>
			</template>
		</CommonHeader>
		<view class="contact">
			<view class="contact-text">
				<text>Welcome contacting us to feedback</text>
			</view>
			<image class="contact-image" src="/static/contact_us.jpeg" />
		</view>
	</view>
</template>
<script setup lang="ts">
import CommonHeader from "@/components/CommonHeader.vue";
import { ref, reactive, onMounted } from "vue";

onMounted(() => {
	uni.setNavigationBarTitle({
		title: 'TalkieAI'
	});
});
/**
 * 回到主页面
 */
const handleBackPage = () => {
	uni.switchTab({
		url: "/pages/my/index",
	});
};
</script>
<style scoped src="./less/index.less" lang="less"></style>
