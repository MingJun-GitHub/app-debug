<script setup lang="ts">
withDefaults(defineProps<{
  icon: string
  title: string
  description: string
}>(), {
  icon: 'i-heroicons-inbox'
})
</script>

<template>
  <UCard
    class="empty-panel"
    :ui="{
      body: {
        base: 'flex h-full items-center justify-center',
        padding: 'p-6 sm:p-8'
      }
    }"
  >
    <div class="empty-panel-content">
      <div class="empty-panel-icon bg-primary-50 text-primary-500 dark:bg-primary-950 dark:text-primary-400">
        <UIcon :name="icon" />
      </div>
      <h2 class="empty-panel-title">{{ title }}</h2>
      <p class="empty-panel-description">{{ description }}</p>
      <slot />
    </div>
  </UCard>
</template>
