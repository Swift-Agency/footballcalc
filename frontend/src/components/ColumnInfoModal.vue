<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="column-info-overlay"
      @click.self="emit('close')"
    >
      <div
        class="column-info-panel"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="titleId"
      >
        <h2 :id="titleId" class="column-info-title">{{ title }}</h2>
        <ul class="column-info-list">
          <li v-for="(line, i) in lines" :key="i" class="column-info-item">
            <span class="column-info-label">{{ line.label }}</span>
            <span class="column-info-sep"> — </span>
            <span>{{ line.text }}</span>
          </li>
        </ul>
        <button type="button" class="column-info-btn" @click="emit('close')">
          Понятно
        </button>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
export interface InfoLine {
  label: string
  text: string
}

defineProps<{
  open: boolean
  title: string
  lines: InfoLine[]
}>()

const emit = defineEmits<{ close: [] }>()

const titleId = 'column-info-modal-title'
</script>

<style scoped>
.column-info-overlay {
  position: fixed;
  inset: 0;
  z-index: 220;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 16px;
}

.column-info-panel {
  width: 100%;
  max-width: 400px;
  margin: 0 auto;
  background: var(--card);
  border-radius: 28px;
  padding: 24px 20px 20px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.18);
}

.column-info-title {
  color: #000;
  font-family: "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 18px;
  font-weight: 700;
  line-height: 24px;
  margin-bottom: 16px;
}

.column-info-list {
  list-style: none;
  margin: 0 0 20px;
  padding: 0;
}

.column-info-item {
  color: #222;
  font-family: "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 14px;
  font-weight: 400;
  line-height: 20px;
  margin-bottom: 10px;
}

.column-info-item:last-child {
  margin-bottom: 0;
}

.column-info-label {
  font-weight: 600;
}

.column-info-btn {
  width: 100%;
  border: none;
  border-radius: 999px;
  padding: 14px 20px;
  background: var(--primary);
  color: #fff;
  font-family: "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 16px;
  font-weight: 600;
  line-height: 22px;
  cursor: pointer;
}

.column-info-btn:active {
  opacity: 0.92;
}
</style>
