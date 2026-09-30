<script setup lang="ts">
import type { ProfileSettingKey, ProfileSettings } from "../types"
import { Switch as VanSwitch } from "vant"
import "vant/es/switch/style/index"

defineProps<{ settings: ProfileSettings }>()

const emit = defineEmits<{ update: [key: ProfileSettingKey, value: boolean] }>()
</script>

<template>
  <section class="panel-card" data-testid="settings-panel">
    <div class="panel-title">
      显示设置
    </div>
    <div class="panel-subtitle">
      只影响本页面的展示效果，保存在当前设备
    </div>
    <div class="setting-row">
      <div class="setting-info">
        <div class="setting-label">
          显示记录时间
        </div>
        <div class="setting-desc">
          在每条历史记录下方显示时间
        </div>
      </div>
      <VanSwitch
        :model-value="settings.showHistoryTime"
        size="22px"
        aria-label="显示记录时间"
        data-testid="setting-show-time"
        @update:model-value="emit('update', 'showHistoryTime', $event)"
      />
    </div>
    <div class="setting-row">
      <div class="setting-info">
        <div class="setting-label">
          默认展开回答
        </div>
        <div class="setting-desc">
          进入页面时自动展开较长的回答内容
        </div>
      </div>
      <VanSwitch
        :model-value="settings.expandAnswers"
        size="22px"
        aria-label="默认展开回答"
        data-testid="setting-expand-answers"
        @update:model-value="emit('update', 'expandAnswers', $event)"
      />
    </div>
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
.setting-row {
  margin-top: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px;
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #fafcff 100%);
  border: 1px solid #edf2f7;
}
.setting-info {
  min-width: 0;
}
.setting-label {
  font-size: 15px;
  font-weight: 700;
  color: #1f2937;
}
.setting-desc {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.7;
  color: #6b7280;
}
</style>
