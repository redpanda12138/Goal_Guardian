import { createSSRApp } from "vue";
import App from "./App.vue";
import { appEventBus } from "@/utils/appEventBus";

const getHeight = (global: any) => {
  uni.getSystemInfo({
    success: (e) => {
      global.StatusBar = e.statusBarHeight || 0;
      // Platform-specific logic
      if (e.platform === "android") {
        global.CustomBar = global.StatusBar + 50;
      } else {
        global.CustomBar = global.StatusBar + 45;
      }
      // MP-WEIXIN specific logic
      // #ifdef MP-WEIXIN
      global.Custom = wx.getMenuButtonBoundingClientRect();
      let customBar =
        global.Custom.bottom + global.Custom.top - global.StatusBar + 4;
      global.CustomBar = customBar;
      // #endif
      // MP-ALIPAY specific logic
      // #ifdef MP-ALIPAY
      const titleBarHeight = e.titleBarHeight || 0;
      global.CustomBar = global.StatusBar + titleBarHeight;
      // #endif
    },
  });
};
export function createApp() {
  const app = createSSRApp(App);
  app.provide("$bus", appEventBus);
  app.config.globalProperties.$bus = appEventBus;
  getHeight(app.config.globalProperties);
  return {
    app,
  };
}
