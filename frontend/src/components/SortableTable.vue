<template>
  <div class="sortable-table-wrapper">
    <div class="table-scroll" :class="{ 'table-scroll--wide': horizontalScroll }">
      <table class="sortable-table">
        <thead>
          <tr>
            <th
              v-for="col in columns"
              :key="col.key"
              :class="[
                col.sortable !== false ? 'sortable' : '',
                sortState.key === col.key ? 'sorted' : '',
                col.align || 'center',
                col.sticky ? 'sticky-col' : '',
              ]"
            :style="col.width ? { width: col.width, minWidth: col.width } : {}"
              @click="col.sortable !== false && toggleSort(col.key)"
            >
              <span class="th-content">
                {{ col.label }}
                <span v-if="col.sortable !== false && sortState.key === col.key" class="sort-arrow">
                  {{ sortState.direction === 'desc' ? '▼' : '▲' }}
                </span>
              </span>
            </th>
          </tr>
        </thead>
        <TransitionGroup name="list" tag="tbody">
          <tr
            v-for="(row, idx) in sortedData"
            :key="rowKey(row)"
            :class="[rowClass ? rowClass(row, idx) : '', { 'tr--clickable': rowClickable }]"
            @click="onRowClick(row, idx)"
          >
            <td
              v-for="col in columns"
              :key="col.key"
              :class="[col.align || 'center', col.sticky ? 'sticky-col' : '']"
              :style="col.width ? { width: col.width, minWidth: col.width } : {}"
            >
              <slot :name="col.key" :row="row" :index="idx" :value="getVal(row, col.key)">
                {{ getVal(row, col.key) }}
              </slot>
            </td>
          </tr>
        </TransitionGroup>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { getTelegram } from '../telegram'
import { postAppEvent } from '../analytics'

export interface Column {
  key: string
  label: string
  sortable?: boolean
  align?: 'left' | 'center' | 'right'
  width?: string
  sticky?: boolean
}

const props = withDefaults(
  defineProps<{
    columns: Column[]
    data: any[]
    defaultSortKey?: string
    defaultSortDir?: 'asc' | 'desc'
    rowKey: (row: any) => string | number
    rowClass?: (row: any, idx: number) => string
    /** When true, allow horizontal scroll (wide tables with many columns). */
    horizontalScroll?: boolean
    /** When true, tbody rows emit rowClick and show pointer cursor. */
    rowClickable?: boolean
  }>(),
  { horizontalScroll: false, rowClickable: false },
)

const emit = defineEmits<{
  rowClick: [row: any, index: number]
}>()

function onRowClick(row: any, index: number) {
  if (!props.rowClickable) return
  emit('rowClick', row, index)
}

const sortState = ref<{ key: string | null; direction: 'asc' | 'desc' | null; clicks: number }>({
  key: props.defaultSortKey || null,
  direction: props.defaultSortDir || 'desc',
  clicks: props.defaultSortKey ? 1 : 0,
})

function toggleSort(key: string) {
  if (sortState.value.key === key) {
    sortState.value.clicks++
    if (sortState.value.clicks === 2) {
      sortState.value.direction = 'asc'
    } else if (sortState.value.clicks >= 3) {
      sortState.value.key = props.defaultSortKey || null
      sortState.value.direction = props.defaultSortDir || 'desc'
      sortState.value.clicks = props.defaultSortKey ? 1 : 0
    }
  } else {
    sortState.value.key = key
    sortState.value.direction = 'desc'
    sortState.value.clicks = 1
  }
}

function getVal(row: any, key: string): any {
  return key.split('.').reduce((o, k) => o?.[k], row)
}

const sortedData = computed(() => {
  const arr = [...props.data]
  const { key, direction } = sortState.value
  if (!key || !direction) return arr

  return arr.sort((a, b) => {
    const va = getVal(a, key)
    const vb = getVal(b, key)
    const cmp = typeof va === 'number' ? va - vb : String(va).localeCompare(String(vb))
    return direction === 'desc' ? -cmp : cmp
  })
})

let _sortDebounce: ReturnType<typeof setTimeout> | null = null
watch(
  sortState,
  () => {
    if (_sortDebounce) clearTimeout(_sortDebounce)
    _sortDebounce = setTimeout(() => {
      const tg = getTelegram()
      const uid = tg?.initDataUnsafe?.user?.id
      postAppEvent(
        'sort_change',
        { key: sortState.value.key, direction: sortState.value.direction },
        typeof uid === 'number' ? uid : undefined,
      )
    }, 500)
  },
  { deep: true },
)
</script>

<style scoped>
.sortable-table-wrapper {
  padding: 0 16px 4px;
  overflow: hidden;
}

.table-scroll {
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
}

.table-scroll--wide {
  overflow-x: auto;
}

.table-scroll--wide .sortable-table {
  min-width: 520px;
  table-layout: auto;
}

.sortable-table {
  width: 100%;
  max-width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 12px;
}

.sortable-table thead {
  background: transparent;
}

.sortable-table th {
  padding: 10px 4px;
  color: #AAB2BD;
  font-family: "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 12px;
  font-style: normal;
  font-weight: 500;
  line-height: normal;
  white-space: nowrap;
  border-bottom: 1px solid var(--border);
  user-select: none;
}

.sortable-table th:first-child {
  padding-left: 4px;
}

.sortable-table th.sortable {
  cursor: pointer;
}

.sortable-table th.sortable:hover {
  color: var(--primary);
}

.sortable-table th.sorted {
  color: var(--primary);
}

.th-content {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.sort-arrow {
  font-size: 8px;
}

.sortable-table td {
  padding: 0 4px;
  border-bottom: 1px solid #E6E9ED;
  color: #222;
  font-family: "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 12px;
  font-style: normal;
  font-weight: 500;
  line-height: normal;
  white-space: nowrap;
  height: 40px;
  vertical-align: middle;
}

.sortable-table td:first-child {
  padding-left: 4px;
}

.sortable-table tbody tr {
  height: 40px;
}

.sortable-table tbody tr.tr--clickable {
  cursor: pointer;
}

.sortable-table tbody tr.tr--clickable:active {
  opacity: 0.92;
}

.sortable-table tr:last-child td {
  border-bottom: none;
}

/* Team column (first column with sticky) can allow text to wrap/ellipsis */
.sortable-table td:first-child {
  white-space: normal;
  overflow: hidden;
}

.sortable-table th:first-child .th-content {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.left { text-align: left; }
.center { text-align: center; }
.right { text-align: right; }

.sticky-col {
  position: sticky;
  left: 0;
  background: var(--card);
  z-index: 1;
}

.list-move {
  transition: transform 0.3s ease;
}
</style>
