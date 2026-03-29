<script setup lang="ts">
interface Props {
  text?: string
}

const props = withDefaults(defineProps<Props>(), {
  text: "一个精心制作的移动端 H5 模板"
})
</script>

<template>
  <div>
    <h1 un-flex-y-center>
      <img src="/favicon.png" un-w-38px un-h-38px>
      <span un-ml-16px un-text-32px un-fw400>MobVue</span>
    </h1>
    <h2 un-color-hex-969799 un-text-14px un-fw400>
      {{ props.text }}
    </h2>
  </div>
</template>
