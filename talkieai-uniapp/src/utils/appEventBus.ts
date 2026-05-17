import EventBus from "./bus";

/** 与 main.ts 注入的 $bus 为同一实例，供 App 生命周期外（如定时器）安全 emit */
export const appEventBus = new EventBus();
