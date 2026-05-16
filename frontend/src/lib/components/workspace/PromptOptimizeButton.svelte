<script lang="ts">
  import { api } from '$lib/api';

  export let value: string;
  export let context: string = 'general';
  export let projectName: string = '';
  export let onOptimized: (optimized: string) => void;

  let loading = false;
  let error = '';

  async function handleOptimize() {
    if (!value.trim() || loading) return;
    loading = true;
    error = '';
    try {
      const result = await api.optimizePrompt({ prompt: value.trim(), context, projectName: projectName.trim() || undefined });
      onOptimized(result.optimized);
    } catch (e: any) {
      error = e.message || '优化失败';
    } finally {
      loading = false;
    }
  }
</script>

<div class="btn-optimize-wrap">
  <button
    class="btn-optimize"
    type="button"
    disabled={!value.trim() || loading}
    on:click={handleOptimize}
  >
    {#if loading}
      <span class="optimize-spinner"></span>
      优化中
    {:else}
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3z"/>
        <path d="M5 18l.75 2.25L8 21l-2.25.75L5 24l-.75-2.25L2 21l2.25-.75L5 18z"/>
        <path d="M19 15l.5 1.5L21 17l-1.5.5L19 19l-.5-1.5L17 17l1.5-.5L19 15z"/>
      </svg>
      提示词优化
    {/if}
  </button>
  {#if error}
    <span class="optimize-error">{error}</span>
  {/if}
</div>

<style>
  .btn-optimize-wrap {
    position: absolute;
    bottom: 8px;
    right: 8px;
    z-index: 2;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .btn-optimize {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    height: 28px;
    padding: 0 10px;
    border-radius: 6px;
    background: rgba(12, 14, 20, 0.85);
    border: 1px solid rgba(196, 181, 253, 0.25);
    color: #f4f1ea;
    font-size: 12px;
    font-weight: 700;
    cursor: pointer;
    transition: .18s ease;
    white-space: nowrap;
    backdrop-filter: blur(8px);
  }
  .btn-optimize:hover:not(:disabled) {
    background: rgba(196, 181, 253, 0.15);
    border-color: rgba(196, 181, 253, 0.4);
    color: #ffffff;
  }
  .btn-optimize:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .optimize-spinner {
    display: inline-block;
    width: 12px;
    height: 12px;
    border: 2px solid rgba(196, 181, 253, 0.3);
    border-top-color: #f4f1ea;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  .optimize-error {
    display: block;
    color: #ff7b8a;
    font-size: 11px;
  }
</style>
