<script setup lang="ts">
import { computed, ref } from "vue"
import { showToast } from "vant"
import { knowledgeFeed, knowledgeCategories } from "@/mock/knowledge"

const activeCategory = ref("全部")
const keyword = ref("")

const categories = computed(() => ["全部", ...knowledgeCategories])

const filteredFeed = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return knowledgeFeed.filter((item) => {
    const matchCategory = activeCategory.value === "全部" || item.category === activeCategory.value
    const matchKeyword = !kw || item.title.toLowerCase().includes(kw) || item.summary.toLowerCase().includes(kw)
    return matchCategory && matchKeyword
  })
})

const openArticle = (title: string) => {
  showToast(`先展示文章详情：${title}`)
}
</script>

<template>
  <div class="home-page">
    <section class="hero-card">
      <div class="hero-top">
        <div>
          <div class="hero-badge">CAMPUS AI</div>
          <h1 class="hero-title">校园智能助手</h1>
          <p class="hero-subtitle">新生须知、选课提醒、图书馆规则与校园政策，一屏快速查看。</p>
        </div>
        <div class="hero-icon">🎓</div>
      </div>

      <div class="hero-search">
        <van-search
          v-model="keyword"
          shape="round"
          placeholder="搜索新生须知、选课、图书馆..."
          background="transparent"
        />
      </div>

      <div class="hero-stats">
        <div class="stat-card">
          <div class="stat-value">6</div>
          <div class="stat-label">知识分类</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ knowledgeFeed.length }}</div>
          <div class="stat-label">推荐内容</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">24h</div>
          <div class="stat-label">随时可查</div>
        </div>
      </div>
    </section>

    <section class="panel-card">
      <div class="panel-head">
        <div>
          <div class="panel-title">快捷分类</div>
          <div class="panel-subtitle">按校园场景浏览内容</div>
        </div>
      </div>

      <div class="category-grid">
        <div
          v-for="item in categories"
          :key="item"
          class="category-chip"
          :class="{ active: activeCategory === item }"
          @click="activeCategory = item"
        >
          {{ item }}
        </div>
      </div>
    </section>

    <section class="panel-card">
      <div class="panel-head">
        <div>
          <div class="panel-title">校园资讯流</div>
          <div class="panel-subtitle">适合展示通知、推文、办事指南和须知类内容</div>
        </div>
        <span class="panel-tag">{{ filteredFeed.length }} 条</span>
      </div>

      <div class="feed-list">
        <article
          v-for="item in filteredFeed"
          :key="item.id"
          class="feed-card"
          @click="openArticle(item.title)"
        >
          <div class="feed-meta">
            <span class="feed-category">{{ item.category }}</span>
            <span class="feed-date">{{ item.date }}</span>
          </div>
          <h3 class="feed-title">{{ item.title }}</h3>
          <p class="feed-summary">{{ item.summary }}</p>
          <div class="feed-footer">
            <span>点击查看详情</span>
            <span class="feed-arrow">→</span>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.home-page {
  min-height: 100%;
  padding: 14px 14px 24px;
  background:
    radial-gradient(circle at top right, rgba(64, 158, 255, 0.18), transparent 26%),
    linear-gradient(180deg, #eef5ff 0%, #f7f9fc 36%, #f7f8fa 100%);
  box-sizing: border-box;
}
.hero-card {
  position: relative;
  overflow: hidden;
  padding: 18px;
  border-radius: 24px;
  background: linear-gradient(135deg, #175fe6 0%, #3d8bfd 54%, #7bb2ff 100%);
  box-shadow: 0 18px 40px rgba(23, 95, 230, 0.22);
  color: #fff;
  margin-bottom: 14px;
}
.hero-card::after {
  content: "";
  position: absolute;
  right: -28px;
  top: -28px;
  width: 120px;
  height: 120px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.14);
}
.hero-top {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.hero-badge {
  display: inline-flex;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  letter-spacing: 0.08em;
  background: rgba(255, 255, 255, 0.18);
  backdrop-filter: blur(8px);
}
.hero-title {
  margin: 12px 0 6px;
  font-size: 26px;
  line-height: 1.2;
  font-weight: 700;
}
.hero-subtitle {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.88);
}
.hero-icon {
  width: 52px;
  height: 52px;
  border-radius: 16px;
  display: grid;
  place-items: center;
  font-size: 26px;
  background: rgba(255, 255, 255, 0.16);
  backdrop-filter: blur(8px);
}
.hero-search {
  position: relative;
  z-index: 1;
  margin-top: 14px;
  padding: 4px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.14);
  backdrop-filter: blur(10px);
}
.hero-stats {
  position: relative;
  z-index: 1;
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.stat-card {
  padding: 12px 10px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.14);
  backdrop-filter: blur(10px);
  text-align: center;
}
.stat-value {
  font-size: 18px;
  font-weight: 700;
}
.stat-label {
  margin-top: 4px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.82);
}
.panel-card {
  padding: 16px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 12px 30px rgba(17, 24, 39, 0.06);
  backdrop-filter: blur(12px);
  margin-bottom: 14px;
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
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
.panel-tag {
  padding: 6px 10px;
  border-radius: 999px;
  background: #eef4ff;
  color: #2563eb;
  font-size: 12px;
  font-weight: 600;
}
.category-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.category-chip {
  padding: 10px 14px;
  border-radius: 14px;
  background: #f4f6f8;
  color: #374151;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.2s ease;
}
.category-chip.active {
  background: linear-gradient(135deg, #2f7cff 0%, #5e9dff 100%);
  color: #fff;
  box-shadow: 0 10px 18px rgba(47, 124, 255, 0.24);
}
.feed-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.feed-card {
  padding: 14px;
  border-radius: 18px;
  border: 1px solid #eef2f7;
  background: linear-gradient(180deg, #ffffff 0%, #fafcff 100%);
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.04);
}
.feed-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.feed-category {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 999px;
  background: #edf4ff;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
}
.feed-date {
  font-size: 12px;
  color: #94a3b8;
}
.feed-title {
  margin: 0;
  font-size: 16px;
  line-height: 1.45;
  color: #111827;
}
.feed-summary {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.8;
  color: #64748b;
}
.feed-footer {
  margin-top: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #2563eb;
  font-size: 13px;
  font-weight: 600;
}
.feed-arrow {
  font-size: 18px;
}
</style>
