<script lang="ts">
  import type { Asset, Project } from '$lib/api';

  export let currentProject: Project | null = null;
  export let assets: Asset[] = [];
  export let assetType: 'all' | Asset['type'] = 'all';
  export let createAsset: () => void | Promise<void>;

  $: filteredAssets = assetType === 'all' ? assets : assets.filter((asset) => asset.type === assetType);
</script>

<div class="panel">
  <div class="panel-head">
    <div>
      <div class="panel-title">角色与场景库</div>
      <div class="panel-subtitle">当前项目：{currentProject?.short_name || '未选择项目'}</div>
    </div>

    <div class="segment">
      <button class:active={assetType === 'all'} on:click={() => (assetType = 'all')}>全部</button>
      <button class:active={assetType === 'character'} on:click={() => (assetType = 'character')}>角色</button>
      <button class:active={assetType === 'scene'} on:click={() => (assetType = 'scene')}>场景</button>
      <button class:active={assetType === 'image'} on:click={() => (assetType = 'image')}>图片</button>
      <button class:active={assetType === 'audio'} on:click={() => (assetType = 'audio')}>声音</button>
    </div>
  </div>

  <div class="panel-body">
    <div class="asset-grid">
      {#each filteredAssets as asset}
        <div class="asset-card">
          <div class={'asset-preview ' + (asset.type === 'scene' ? 'scene' : asset.type === 'audio' ? 'audio' : 'person')}>
            {#if asset.image}
              <img class="asset-image" src={asset.image} alt={asset.name} />
            {:else if asset.type !== 'scene'}
              <div class="portrait">{asset.initial}</div>
            {/if}
          </div>

          <div class="asset-body">
            <div class="asset-name">{asset.name}</div>
            <div class="asset-desc">{asset.description}</div>
            <div class="asset-foot"><span>{asset.ref_count} 张参考</span><button class="btn btn-text">查看</button></div>
          </div>
        </div>
      {/each}

      <button class="empty-card" on:click={createAsset}>
        <div><b>新增素材</b><span>上传参考图，或根据剧情创建角色和场景。</span></div>
      </button>
    </div>
  </div>
</div>
