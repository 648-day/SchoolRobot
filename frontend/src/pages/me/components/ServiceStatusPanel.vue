<script setup lang="ts">
import type { HealthInfo } from "@/types/chat"
import { Button as VanButton, Loading as VanLoading } from "vant"
import { computed } from "vue"
import "vant/es/button/style/index"
import "vant/es/loading/style/index"

const props = defineProps<{
  status: "loading" | "ok" | "error"
  info: HealthInfo | null
}>()

const emit = defineEmits<{ refresh: [] }>()

const RETRIEVAL_MODE_TEXT: Record<string, string> = {
  keyword: "关键词",
  chroma: "向量"
}

const modeText = computed(() => {
  if (props.status !== "ok" || !props.info) return "未知"
  return RETRIEVAL_MODE_TEXT[props.info.retrievalMode] ?? "未知"
})

const errorText = computed(() => {
  if (props.info && props.info.status !== "ok") return `服务异常（${props.info.status}）`
  return "无法连接"
})
</script>

<template>
  <section class="panel-card" data-testid="service-panel">
    <div class="panel-head">
      <div class="panel-head-text">
        <div class="panel-title">
          服务状态
        </div>
        <div class="panel-subtitle">
          仅表示后端服务连接情况
        </div>
      </div>
      <VanButton
        size="small"
        plain
        type="primary"
        data-testid="service-refresh"
        :loading="status === 'loading'"
        @click="emit('refresh')"
      >
        重新检测
      </VanButton>
    </div>

    <div v-if="status === 'loading'" class="service-loading" data-testid="service-loading">
      <VanLoading size="18">
        正在检测服务连接…
      </VanLoading>
    </div>

    <template v-else-if="status === 'ok'">
      <div class="service-row">
        <span class="service-label">连接状态</span>
        <span class="service-value is-ok" data-testid="service-status">在线</span>
      </div>
      <div class="service-row">
        <span class="service-label">检索模式</span>
        <span class="service-value" data-testid="service-mode">{{ modeText }}</span>
      </div>
      <div v-if="info?.model" class="service-row">
        <span class="service-label">配置模型</span>
        <span class="service-value" data-testid="service-model">{{ info.model }}</span>
      </div>
      <p class="service-note" data-testid="service-note">
        仅表示后端服务连接正常，不代表问答与检索的依赖均可用。
      </p>
    </template>

    <template v-else>
      <div class="service-row">
        <span class="service-label">连接状态</span>
        <span class="service-value is-error" data-testid="service-status">{{ errorText }}</span>
      </div>
      <div class="service-row">
        <span class="service-label">检索模式</span>
        <span class="service-value" data-testid="service-mode">未知</span>
      </div>
      <p class="service-note" data-testid="service-note">
        健康检查失败：请确认后端服务已启动且网络可用。
      </p>
    </template>
  </section>
</template>

<style scoped>
.panel-card {
  margin-top: 14px;
  padding: 16px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.06);
}
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.panel-head-text {
  min-width: 0;
}
.panel-title {
  font-size: 17px;
  font-weight: 700;
  color: #1f2937;
}
.panel-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: #6b7280;
}
.service-loading {
  margin-top: 14px;
  display: flex;
  justify-content: center;
}
.service-row {
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-size: 14px;
}
.service-label {
  color: #64748b;
}
.service-value {
  font-weight: 700;
  color: #1f2937;
  overflow-wrap: anywhere;
  text-align: right;
}
.service-value.is-ok {
  color: #16a34a;
}
.service-value.is-error {
  color: #dc2626;
}
.service-note {
  margin: 12px 0 0;
  font-size: 12px;
  line-height: 1.7;
  color: #94a3b8;
}
</style>
