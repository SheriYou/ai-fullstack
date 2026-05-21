<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { createTodo, listTodos, type Todo } from './api'

const todos = ref<Todo[]>([])
const title = ref('')
const loading = ref(false)
const error = ref<string | null>(null)

async function refresh() {
  error.value = null
  loading.value = true
  try {
    todos.value = await listTodos()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (!title.value.trim()) return
  error.value = null
  loading.value = true
  try {
    await createTodo(title.value.trim())
    title.value = ''
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(refresh)
</script>

<template>
  <div class="min-h-screen">
    <div class="mx-auto max-w-3xl px-4 py-10">
      <div class="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
        <div class="flex items-start justify-between gap-4">
          <div>
            <h1 class="text-xl font-semibold tracking-tight">ai-fullstack demo</h1>
            <p class="mt-1 text-sm text-slate-600">
              Vue3 + Tailwind → 调用 Spring Boot API → 写入 MySQL（启动自动建库&填充 demo）
            </p>
          </div>
          <button
            class="rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60"
            :disabled="loading"
            @click="refresh"
          >
            刷新
          </button>
        </div>

        <form class="mt-6 flex gap-3" @submit.prevent="submit">
          <input
            v-model="title"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-900"
            placeholder="新增一个 todo，例如：Build fullstack demo"
          />
          <button
            class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-60"
            :disabled="loading || !title.trim()"
            type="submit"
          >
            添加
          </button>
        </form>

        <div v-if="error" class="mt-4 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700 ring-1 ring-rose-100">
          {{ error }}
        </div>

        <div class="mt-6">
          <div class="mb-2 text-xs font-medium text-slate-500">Todos</div>
          <div v-if="loading && !todos.length" class="text-sm text-slate-600">加载中…</div>
          <ul v-else class="space-y-2">
            <li
              v-for="t in todos"
              :key="t.id"
              class="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3"
            >
              <div class="min-w-0">
                <div class="truncate text-sm font-medium">
                  <span :class="t.completed ? 'line-through text-slate-400' : ''">
                    {{ t.title }}
                  </span>
                </div>
                <div class="mt-1 text-xs text-slate-500">
                  #{{ t.id }} · {{ new Date(t.createdAt).toLocaleString() }}
                </div>
              </div>
              <span
                class="shrink-0 rounded-full px-2 py-1 text-xs font-medium"
                :class="t.completed ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'"
              >
                {{ t.completed ? 'Done' : 'Todo' }}
              </span>
            </li>
          </ul>
        </div>
      </div>
      <p class="mt-6 text-center text-xs text-slate-500">
        API: <code class="rounded bg-slate-100 px-1 py-0.5">/api/todos</code>
      </p>
    </div>
  </div>
</template>

