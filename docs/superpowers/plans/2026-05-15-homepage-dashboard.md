# 120JPH Homepage Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the frontend empty state into a rich, interactive Homepage Dashboard that dynamically loads skills from the backend and allows users to directly initiate a conversation from the homepage.

**Architecture:** 
1. Expose existing domain/scenario registry data via a new FastAPI `GET /api/chat/skills` endpoint.
2. Introduce a Pinia `skills` store in the Vue 3 frontend to fetch and cache these capabilities.
3. Replace `EmptyState.vue` with `WelcomeDashboard.vue` (based on the prototype).
4. Update `ChatView.vue` to listen for a `submit` event from `WelcomeDashboard`. If triggered, `ChatView` automatically calls the session creation API, switches state, and dispatches the message.

**Tech Stack:** FastAPI, Vue 3, Pinia, Tailwind CSS

---

## User Review Required

> [!IMPORTANT]
> - **Error Handling**: If the `/api/chat/skills` request fails, the dashboard will gracefully fall back to a hardcoded fallback or simply show an empty state. Is this acceptable?
> - **Session Title**: When auto-creating a session from the homepage, the plan is to use the first 15 characters of the prompt as the session title. Is this fine?

---

### Task 1: Backend API - Expose Skills Data

**Files:**
- Modify: `backend/app/api.py`

- [ ] **Step 1: Add the `/api/chat/skills` endpoint in `api.py`**

```python
from backend.app.skills.registry import DOMAIN_SKILLS
import backend.app.skills.registry

@router.get("/skills")
def get_skills_endpoint():
    """获取所有已注册的领域和场景技能"""
    skills_list = []
    for domain_name, domain_info in DOMAIN_SKILLS.items():
        skills_list.append({
            "name": domain_info["name"],
            "title": domain_info.get("name", domain_info["name"]), # We'll map UI titles
            "description": domain_info["description"],
            "scenarios": [
                {
                    "name": s["name"],
                    "title": s.get("name", s["name"]),
                    "description": s.get("description", ""),
                    "questions": s.get("parameters", {}).get("example_questions", []) 
                }
                for s in backend.app.skills.registry.list_scenarios_by_skill(domain_info["name"])
            ]
        })
    return skills_list
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/api.py
git commit -m "feat: add GET /api/chat/skills endpoint"
```

---

### Task 2: Frontend Data Layer - Skills Store

**Files:**
- Create: `frontend/src/stores/skills.ts`

- [ ] **Step 1: Create the Pinia store for skills**

```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSkillsStore = defineStore('skills', () => {
  const domains = ref<any[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const fetchSkills = async () => {
    if (domains.value.length > 0) return
    isLoading.value = true
    try {
      const response = await fetch('http://localhost:8000/api/chat/skills')
      if (!response.ok) throw new Error('Failed to fetch skills')
      const data = await response.json()
      domains.value = data
    } catch (err: any) {
      error.value = err.message
      console.error(err)
    } finally {
      isLoading.value = false
    }
  }

  return { domains, isLoading, error, fetchSkills }
})
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/stores/skills.ts
git commit -m "feat: add pinia store for skills"
```

---

### Task 3: Frontend UI - WelcomeDashboard Component

**Files:**
- Create: `frontend/src/components/WelcomeDashboard.vue`
- Delete: `frontend/src/components/EmptyState.vue`
- Delete: `frontend/src/components/PrototypeDashboard.vue`

- [ ] **Step 1: Implement `WelcomeDashboard.vue`**
*(This will be the code from `PrototypeDashboard.vue`, but hooked to `useSkillsStore` and emitting events)*

```vue
<template>
  <div class="relative flex flex-1 flex-col items-center overflow-y-auto px-4 pb-20 pt-12">
    <!-- UI contents from prototype ... -->
    <div class="relative flex items-center ...">
      <input 
        v-model="localInput"
        @keydown.enter="handleSubmit(localInput)"
        type="text" 
        placeholder="在此直接提问..." 
        class="..."
      />
    </div>
    <!-- Loops over skillsStore.domains -->
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSkillsStore } from '@/stores/skills'

const emit = defineEmits<{
  (e: 'submit', prompt: string): void
}>()

const localInput = ref('')
const skillsStore = useSkillsStore()

onMounted(() => {
  skillsStore.fetchSkills()
})

const handleSubmit = (prompt: string) => {
  if (!prompt.trim()) return
  emit('submit', prompt.trim())
}
</script>
```

- [ ] **Step 2: Commit**

```bash
git rm frontend/src/components/EmptyState.vue frontend/src/components/PrototypeDashboard.vue
git add frontend/src/components/WelcomeDashboard.vue
git commit -m "feat: implement WelcomeDashboard UI"
```

---

### Task 4: Frontend Logic - ChatView Integration

**Files:**
- Modify: `frontend/src/views/ChatView.vue`

- [ ] **Step 1: Replace Prototype with WelcomeDashboard and handle the new submission event**

```vue
<!-- Template changes: -->
<WelcomeDashboard v-else @submit="handleDashboardSubmit" />
```

```typescript
// Script changes:
import WelcomeDashboard from '@/components/WelcomeDashboard.vue'

const handleDashboardSubmit = async (prompt: string) => {
  if (isSending.value) return
  
  // Create a new session on the fly
  const title = prompt.length > 15 ? prompt.substring(0, 15) + '...' : prompt
  await sessionsStore.createSession({ title })
  
  // Set the input text and send message immediately
  inputText.value = prompt
  await handleSendMessage()
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/ChatView.vue
git commit -m "feat: integrate WelcomeDashboard and auto-session creation"
```
