<template>
  <div class="venue-filter">
    <button
      v-for="opt in options"
      :key="opt.value"
      :class="{ active: modelValue === opt.value }"
      @click="$emit('update:modelValue', opt.value)"
    >
      {{ opt.label }}
    </button>
  </div>
</template>

<script setup lang="ts">
import type { VenueType } from '../api'

defineProps<{ modelValue: VenueType }>()
defineEmits<{ 'update:modelValue': [value: VenueType] }>()

const options = [
  { value: 'all' as VenueType, label: 'Все матчи' },
  { value: 'home' as VenueType, label: 'Дома' },
  { value: 'away' as VenueType, label: 'На выезде' },
]
</script>
