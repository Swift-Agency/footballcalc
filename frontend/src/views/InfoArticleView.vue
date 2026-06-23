<template>
  <div class="page">
    <div class="info-hero">
      <h1 class="hero-title">{{ title }}</h1>
    </div>

    <article v-if="htmlContent" class="article-card markdown-body" v-html="htmlContent" />
    <p v-else-if="loading" class="loading">Загрузка...</p>
    <p v-else class="loading">Раздел не найден</p>
  </div>
</template>

<script setup lang="ts">
/**
 * Article HTML is produced only from bundled static files under /public/info/*.md.
 * Do not point loadArticle at untrusted URLs or user-controlled paths.
 */
import { computed, onMounted, ref, watch } from 'vue'

const props = defineProps<{ slug: string }>()
const loading = ref(false)
const markdown = ref('')

const TITLES: Record<string, string> = {
  faq: 'Вопросы и ответы',
  glossary: 'Глоссарий терминов',
  other: 'Другое',
}

const title = computed(() => TITLES[props.slug] ?? 'Информация')
const htmlContent = computed(() => (markdown.value ? renderMarkdown(markdown.value) : ''))

async function loadArticle() {
  loading.value = true
  markdown.value = ''
  try {
    const resp = await fetch(`/info/${props.slug}.md`)
    if (!resp.ok) return
    markdown.value = await resp.text()
  } finally {
    loading.value = false
  }
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function renderInline(value: string): string {
  let out = escapeHtml(value)
  out = out.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  out = out.replace(/\*(.+?)\*/g, '<em>$1</em>')
  out = out.replace(/`(.+?)`/g, '<code>$1</code>')
  out = out.replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
  return out
}

function renderMarkdown(md: string): string {
  const lines = md.replace(/\r\n/g, '\n').split('\n')
  const html: string[] = []
  let inList = false

  const closeList = () => {
    if (inList) {
      html.push('</ul>')
      inList = false
    }
  }

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) {
      closeList()
      continue
    }

    if (trimmed.startsWith('- ')) {
      if (!inList) {
        html.push('<ul>')
        inList = true
      }
      html.push(`<li>${renderInline(trimmed.slice(2))}</li>`)
      continue
    }

    closeList()

    if (trimmed.startsWith('### ')) {
      html.push(`<h3>${renderInline(trimmed.slice(4))}</h3>`)
      continue
    }
    if (trimmed.startsWith('## ')) {
      html.push(`<h2>${renderInline(trimmed.slice(3))}</h2>`)
      continue
    }
    if (trimmed.startsWith('# ')) {
      html.push(`<h1>${renderInline(trimmed.slice(2))}</h1>`)
      continue
    }

    html.push(`<p>${renderInline(trimmed)}</p>`)
  }

  closeList()
  return html.join('\n')
}

watch(() => props.slug, () => {
  loadArticle()
})

onMounted(() => {
  loadArticle()
})
</script>

<style scoped>
.info-hero {
  box-sizing: border-box;
  height: calc(var(--page-header-height) + var(--app-safe-top) + var(--header-title-offset));
  padding: calc(var(--app-safe-top) + var(--header-title-offset)) 24px 0;
  border-radius: 0 0 24px 24px;
  background: linear-gradient(160deg, var(--primary) 0%, var(--primary-light) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.hero-title {
  color: #fff;
  font-size: 22px;
  font-weight: 700;
  line-height: 1.2;
  text-align: center;
}

.article-card {
  background: var(--card);
  border-radius: var(--radius);
  margin: 12px;
  padding: 18px 20px;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  color: #111827;
  margin: 0 0 12px;
  line-height: 1.25;
}

.markdown-body :deep(h1) {
  font-size: 22px;
}

.markdown-body :deep(h2) {
  font-size: 18px;
}

.markdown-body :deep(h3) {
  font-size: 16px;
}

.markdown-body :deep(p) {
  color: #1f2937;
  font-size: 15px;
  line-height: 1.45;
  margin: 0 0 12px;
}

.markdown-body :deep(ul) {
  margin: 0 0 14px;
  padding-left: 20px;
}

.markdown-body :deep(li) {
  color: #1f2937;
  font-size: 15px;
  line-height: 1.45;
  margin-bottom: 6px;
}

.markdown-body :deep(code) {
  background: #eef2ff;
  border-radius: 4px;
  padding: 1px 5px;
  font-size: 13px;
}

.markdown-body :deep(a) {
  color: var(--primary);
  text-decoration: none;
}
</style>
