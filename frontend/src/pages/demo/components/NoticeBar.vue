<script setup lang="ts">
interface Props {
  text: string
}

const props = defineProps<Props>()
</script>

<template>
  <van-notice-bar
    color="var(--mobvue-primary-color)"
    background="#ecf9ff"
    left-icon="bulb-o"
    :text="props.text"
  />
</template>
