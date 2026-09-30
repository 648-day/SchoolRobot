<script setup lang="ts">
import { Button as VanButton } from "vant"
import { ref } from "vue"
import "vant/es/button/style/index"

const expanded = ref(false)
</script>

<template>
  <section class="panel-card" data-testid="about-panel">
    <div class="panel-head">
      <div class="panel-head-text">
        <div class="panel-title">
          关于我们
        </div>
        <div class="panel-subtitle">
          项目用途、现阶段能力与使用说明
        </div>
      </div>
      <VanButton
        size="small"
        plain
        type="primary"
        data-testid="about-toggle"
        :aria-expanded="expanded"
        @click="expanded = !expanded"
      >
        {{ expanded ? "收起" : "展开" }}
      </VanButton>
    </div>

    <div v-if="expanded" class="about-body" data-testid="about-detail">
      <p class="about-item">
        本项目是校园信息查询工具，基于学校现有资料回答问题，帮助同学快速查找校内常见信息。
      </p>
      <p class="about-item">
        现阶段支持基于学校现有资料的问答：资料中有相关内容时给出回答；缺少相关依据时提示咨询学校相关部门。历史记录等其它能力的可用状态以页面上实际显示为准。
      </p>
      <p class="about-item">
        回答由系统自动生成，可能存在遗漏或不准确，仅供参考；涉及具体政策、时间与手续时，请以学校最新通知和老师答复为准。
      </p>
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
.about-body {
  margin-top: 12px;
}
.about-item {
  margin: 0;
  padding: 10px 12px;
  border-radius: 14px;
  background: #f8fbff;
  border: 1px solid #edf2f7;
  font-size: 13px;
  line-height: 1.8;
  color: #475569;
}
.about-item + .about-item {
  margin-top: 10px;
}
</style>
