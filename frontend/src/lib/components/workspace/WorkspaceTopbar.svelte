<script lang="ts">
  import { pageMeta, type PageKey } from '$lib/workspace/ui';

  export let activePage: PageKey;
  export let setPage: (page: PageKey) => void | Promise<void>;
  export let batchGenerateVideos: () => void | Promise<void>;
  export let refreshDashboard: () => void | Promise<void>;
  export let handleTopAction: () => void | Promise<void>;

  $: currentMeta = pageMeta[activePage];
</script>

<div class="topbar">
  <div>
    <div class="crumbs"><span>工作台</span><span>/</span><strong>{currentMeta.title}</strong></div>
    <div class="sub-context">{currentMeta.description}</div>
  </div>

  <div class="top-actions">
    <div class="search">搜索项目、剧集、素材</div>

    {#if activePage === 'script'}
      <button class="btn btn-secondary" on:click={() => setPage('episodes')}>返回剧集</button>
    {/if}

    {#if activePage === 'video'}
      <button class="btn btn-secondary" on:click={batchGenerateVideos}>批量生成</button>
    {/if}

    {#if activePage === 'account'}
      <button class="btn btn-secondary" on:click={refreshDashboard}>刷新积分</button>
    {/if}

    {#if activePage !== 'account'}
      <button class="btn btn-primary" on:click={handleTopAction}>{currentMeta.actionLabel}</button>
    {/if}
  </div>
</div>
