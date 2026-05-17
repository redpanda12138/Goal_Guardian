<template>
  <Speech
    @completed="(e) => emit('completed', e)"
    @delete="emit('delete')"
    @send="(e) => emit('send', e)"
    ref="speechRef"
  >
    <template v-slot:leftMenu>
      <slot name="leftMenu"></slot>
    </template>
    <template v-slot:rightMenu>
      <slot name="rightMenu"></slot>
    </template>
  </Speech>
</template>
<script setup lang="ts">
import Speech from "@/components/Speech.vue";

const emit = defineEmits<{
  (e: "completed", payload: { fileName: string }): void;
  (e: "delete"): void;
  (e: "send", payload: { fileName: string }): void;
}>();
</script>