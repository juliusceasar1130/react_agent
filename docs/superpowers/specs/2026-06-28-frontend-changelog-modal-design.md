# Frontend Version Changelog Modal Design Specification

This document details the design and specifications for a frontend version release log (Changelog) modal dialog. This modal allows users to review the application's history, current state, new features, improvements, and bug fixes in a high-fidelity glassmorphic multi-column layout.

---

## 1. Goal Description

Create a premium, responsive version changelog modal in the frontend workspace of the model chat application.
*   **Trigger**: Manually clicked by the user (typically in the settings panel or header).
*   **Format**: Left-right multi-column split layout.
    *   **Left Column**: A vertical timeline list showing version tags (`v1.1.0`, `v1.0.0`, etc.) with status indicators.
    *   **Right Column**: An interactive, animated viewport detailing the selected version's features, optimizations, and bug fixes under stylized categorization cards.

---

## 2. Component Design & Interfaces

### Component Path
`[NEW]` `frontend/src/components/VersionChangelogModal.vue`

### Type Definitions
```typescript
export interface ChangelogItem {
  version: string;
  date: string;
  type: 'latest' | 'major' | 'regular';
  summary?: string;
  content: {
    features?: string[];     // New Features 🎉
    improvements?: string[]; // Performance/UX Improvements ⚡
    fixes?: string[];        // Bug Fixes 🐛
  };
}
```

### Properties (Props)
*   `show`: `boolean` (supports `v-model:show`)
*   `data`: `ChangelogItem[]` (Optional, defaults to preloaded Mock data)

---

## 3. Styling & Aesthetics (Tailwind CSS)

To match the existing styling of the application, the modal employs **Glassmorphism**, smooth drop-shadows, and micro-interactions:

### 3.1 Overlay & Modal Wrapper
*   **Overlay Mask**: `bg-black/30 backdrop-blur-md transition-all duration-300`
*   **Modal Frame**: `bg-white/80 dark:bg-neutral-900/80 backdrop-blur-2xl border border-white/20 dark:border-neutral-800 shadow-2xl rounded-[28px] max-w-4xl w-full h-[600px] flex overflow-hidden`

### 3.2 Left Column (Version Timeline)
*   **Width**: `w-1/3 border-r border-neutral-100/80 dark:border-neutral-800`
*   **Track Line**: A centered thin line `w-[1px] bg-neutral-200/60` connecting all version bullets.
*   **Version Bullet (Status indicator)**:
    *   `latest`: `bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.6)]` (Green pulsing dot)
    *   `major`: `bg-blue-500 animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.6)]` (Blue pulsing dot)
    *   `regular`: `bg-neutral-400 dark:bg-neutral-500` (Static gray dot)
*   **ListItem Interaction**: Hover states should translate the list item slightly, applying `bg-neutral-50/80` or `bg-primary/5` with a smooth left-border indicator on selection.

### 3.3 Right Column (Content Cards)
*   **Features Card**: `bg-gradient-to-br from-emerald-50/60 to-white/40 dark:from-emerald-950/20 dark:to-neutral-900/40 border border-emerald-100/80 dark:border-emerald-900/50 rounded-2xl p-4`
*   **Improvements Card**: `bg-gradient-to-br from-amber-50/60 to-white/40 dark:from-amber-950/20 dark:to-neutral-900/40 border border-amber-100/80 dark:border-amber-900/50 rounded-2xl p-4`
*   **Fixes Card**: `bg-gradient-to-br from-rose-50/60 to-white/40 dark:from-rose-950/20 dark:to-neutral-900/40 border border-rose-100/80 dark:border-rose-900/50 rounded-2xl p-4`
*   **Transitions**: Uses Vue's `<Transition name="slide-fade" mode="out-in">` to translate-y and fade content smoothly on tab selection.

---

## 4. Integration Points

### 4.1 Trigger Button Location
Modify `[MODIFY]` `frontend/src/views/ChatView.vue`.
Insert a version button to the header section:
```vue
<button
  @click="showChangelog = true"
  class="flex items-center gap-1.5 rounded-full border border-neutral-200 bg-white px-3 py-2 text-xs font-medium text-neutral-600 transition-all duration-200 hover:bg-neutral-50 hover:text-text shadow-sm whitespace-nowrap"
>
  <span>🚀</span>
  <span>版本说明</span>
</button>
```

### 4.2 Close Interactions
1. Clicking outside the modal container.
2. Clicking the close (✕) button in the upper-right corner.
3. Keyboard event handler for the `Esc` key.
4. Prevents scroll leak on the document body when open.

---

## 5. Verification Plan

### Manual Verification
1. Click the "版本说明" button in the ChatView Header and verify the modal appears with backdrop blur.
2. Cycle through different versions in the left pane and verify that the right-pane updates correctly with slide-fade transition effects.
3. Verify that the modal closes correctly on clicking overlay, "X" icon, or pressing the `Esc` key.
4. Check layout responsiveness on tablet/mobile screens.
