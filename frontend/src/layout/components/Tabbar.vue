<script setup lang="ts">
const router = useRouter()

const tabbarItemList = computed(() => {
  const routes = router.getRoutes()
  return routes.filter(route => route.meta.layout?.tabbar?.showTabbar).map(route => ({
    title: route.meta.title,
    icon: route.meta.layout?.tabbar?.icon,
    path: route.path
  }))
})
</script>

<template>
  <van-tabbar
    route
    fixed
    placeholder
    safe-area-inset-bottom
  >
    <van-tabbar-item
      v-for="item in tabbarItemList"
      :key="item.path"
      :icon="item.icon"
      :to="item.path"
      replace
    >
      {{ item.title }}
    </van-tabbar-item>
  </van-tabbar>
</template>
