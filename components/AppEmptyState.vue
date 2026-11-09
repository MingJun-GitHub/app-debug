<script setup lang="ts">
withDefaults(defineProps<{
  icon: string
  title: string
  description: string
  label?: string
  meta?: string
}>(), {
  icon: 'i-heroicons-inbox',
  label: '',
  meta: ''
})
</script>

<template>
  <UCard
    class="empty-panel"
    :ui="{
      body: {
        base: 'empty-panel-body',
        padding: 'p-0 sm:p-0'
      }
    }"
  >
    <div v-if="label" class="empty-panel-rail">
      <span class="empty-panel-led" aria-hidden="true" />
      <span>{{ label }}</span>
      <span class="empty-panel-meta">{{ meta }}</span>
    </div>
    <div class="empty-panel-content">
      <div class="empty-panel-icon">
        <UIcon :name="icon" />
      </div>
      <h2 class="empty-panel-title">{{ title }}</h2>
      <p class="empty-panel-description">{{ description }}</p>
      <slot />
    </div>
  </UCard>
</template>
