<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchHealth } from '@/api/health'

// 骨架占位页：开机即调后端 /health，用来肉眼确认「前端 → vite proxy → 后端 → Postgres」整条链路是否打通。
type State = 'loading' | 'ok' | 'error'

const state = ref<State>('loading')
const detail = ref('')

onMounted(async () => {
  try {
    const health = await fetchHealth()
    state.value = health.status === 'ok' ? 'ok' : 'error'
    detail.value = `status=${health.status} · db=${health.db}`
  } catch (e) {
    state.value = 'error'
    detail.value = e instanceof Error ? e.message : String(e)
  }
})
</script>

<template>
  <main class="home">
    <h1>Infinite Studio</h1>
    <p class="subtitle">万能 AI 工坊 · 骨架页</p>

    <section class="health" :data-state="state">
      <span class="dot" />
      <span v-if="state === 'loading'">后端健康：检查中…</span>
      <span v-else-if="state === 'ok'">后端健康：ok（{{ detail }}）</span>
      <span v-else>后端不可达：{{ detail }}</span>
    </section>
  </main>
</template>

<style scoped>
.home {
  max-width: 640px;
  margin: 4rem auto;
  padding: 0 1rem;
}
.subtitle {
  color: var(--color-text, #888);
  margin-top: 0.25rem;
}
.health {
  margin-top: 2rem;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.9rem;
  border-radius: 8px;
  border: 1px solid var(--color-border, #ddd);
  font-variant-numeric: tabular-nums;
}
.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #c9a227;
}
.health[data-state='ok'] .dot {
  background: #2ecc71;
}
.health[data-state='error'] .dot {
  background: #e74c3c;
}
</style>
