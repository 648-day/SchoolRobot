<script setup lang="ts">
import { ref, computed } from "vue"
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
  showToast(`这里先展示：${title}`)
}
</script>

<template>
  <div class="home-page">
    <div class="hero-card">
      <div class="hero-title">校园智能助手</div>
      <div class="hero-subtitle">查看新生须知、选课提醒、图书馆规则等校园资讯</div>
      <van-search v-model="keyword" shape="round" placeholder="搜索通知、须知、办事指南" />
    </div>

    <div class="section-card">
      <div class="section-title">分类</div>
      <div class="category-list">
        <van-button
          v-for="item in categories"
          :key="item"
          size="small"
          round
          :type="activeCategory === item ? 'primary' : 'default'"
          @click="activeCategory = item"
        >
          {{ item }}
        </van-button>
      </div>
    </div>

    <div class="section-card">
      <div class="section-title">校园推文</div>
      <div class="feed-list">
        <div v-for="item in filteredFeed" :key="item.id" class="feed-item" @click="openArticle(item.title)">
          <div class="feed-head">
            <span class="feed-category">{{ item.category }}</span>
            <span class="feed-date">{{ item.date }}</span>
          </div>
          <div class="feed-title">{{ item.title }}</div>
          <div class="feed-summary">{{ item.summary }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home-page {
  min-height: 100%;
  padding: 12px 12px 24px;
  background: #f7f8fa;
  box-sizing: border-box;
}
.hero-card,
.section-card {
  background: #fff;
  border-radius: 16px;
  padding: 14px;
  margin-bottom: 12px;
}
.hero-title {
  font-size: 20px;
  font-weight: 700;
  color: #1f2329;
}
.hero-subtitle {
  margin: 8px 0 12px;
  font-size: 13px;
  color: #646566;
  line-height: 1.6;
}
.section-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2329;
  margin-bottom: 12px;
}
.category-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.feed-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.feed-item {
  border: 1px solid #f0f0f0;
  border-radius: 12px;
  padding: 12px;
}
.feed-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.feed-category {
  font-size: 12px;
  color: #1989fa;
  font-weight: 600;
}
.feed-date {
  font-size: 12px;
  color: #969799;
}
.feed-title {
  font-size: 15px;
  font-weight: 700;
  color: #323233;
  margin-bottom: 8px;
}
.feed-summary {
  font-size: 13px;
  color: #646566;
  line-height: 1.7;
}
</style>
