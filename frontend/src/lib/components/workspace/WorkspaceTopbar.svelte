<script lang="ts">
  import { pageMeta, type PageKey } from '$lib/workspace/ui';

  export let activePage: PageKey;
  export let setPage: (page: PageKey) => void | Promise<void>;
  export let batchGenerateVideos: () => void | Promise<void>;
  export let refreshDashboard: () => void | Promise<void>;
  export let handleTopAction: () => void | Promise<void>;

  const mobileNav: Array<{ key: PageKey; label: string }> = [
    { key: 'projects', label: '宇宙' },
    { key: 'episodes', label: '剧集' },
    { key: 'script', label: '分镜' },
    { key: 'assets', label: '素材' },
    { key: 'video', label: '成片' },
    { key: 'account', label: '账户' }
  ];

  $: currentMeta = pageMeta[activePage];
</script>

<div class="topbar">
  <div class="topbar-copy">
    <div class="crumbs"><span>工作室</span><span>/</span><strong>{currentMeta.title}</strong></div>
    <div class="sub-context">{currentMeta.description}</div>
  </div>

  <div class="top-actions">
    <div class="search">搜索项目、剧集、角色或场景</div>

    {#if activePage === 'script'}
      <button class="btn btn-secondary" on:click={() => setPage('episodes')}>返回剧集</button>
    {/if}

    {#if activePage === 'video'}
      <button class="btn btn-secondary" on:click={batchGenerateVideos}>批量生成</button>
    {/if}

    {#if activePage === 'account'}
      <button class="btn btn-secondary" on:click={refreshDashboard}>刷新额度</button>
    {/if}

    {#if activePage !== 'account'}
      <button class="btn btn-primary" on:click={handleTopAction}>{currentMeta.actionLabel}</button>
    {/if}
  </div>

  <div class="mobile-tabbar" aria-label="移动端导航">
    {#each mobileNav as item}
      <button class:active={activePage === item.key} on:click={() => setPage(item.key)}>{item.label}</button>
    {/each}
  </div>
</div>
