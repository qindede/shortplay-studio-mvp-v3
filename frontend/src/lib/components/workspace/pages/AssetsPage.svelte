<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { Asset, AssetReference, Project } from '$lib/api';

  export let currentProject: Project | null = null;
  export let assets: Asset[] = [];
  export let assetType: 'all' | Asset['type'] = 'all';
  export let createAsset: () => void | Promise<void>;

  const dispatch = createEventDispatcher<{ deleteAsset: Asset }>();

  let detailAsset: Asset | null = null;
  let selectedRefIndex = 0;

  $: filteredAssets = assetType === 'all' ? assets : assets.filter((asset) => asset.type === assetType);
  $: detailRefs = detailAsset ? getAssetReferences(detailAsset) : [];
  $: selectedRef = detailRefs[selectedRefIndex] || detailRefs[0];

  function getAssetTypeLabel(type: Asset['type']) {
    return {
      character: '角色',
      scene: '场景',
      image: '图片',
      audio: '声音'
    }[type];
  }

  function getAssetPreviewClass(asset: Asset) {
    return asset.type === 'scene' ? 'scene' : asset.type === 'audio' ? 'audio' : 'person';
  }

  function getAssetReferences(asset: Asset): AssetReference[] {
    if (asset.references?.length) return asset.references;
    if (asset.image) {
      return [{ id: `${asset.id}_image`, type: 'image', name: '主参考', url: asset.image, note: asset.description }];
    }

    const count = Math.max(asset.ref_count || 0, 1);
    return Array.from({ length: count }, (_, index) => ({
      id: `${asset.id}_ref_${index + 1}`,
      type: asset.type === 'audio' ? 'audio' : 'image',
      name: `${getAssetTypeLabel(asset.type)}参考 ${String(index + 1).padStart(2, '0')}`,
      note: asset.description
    }));
  }

  function openAssetDetail(asset: Asset) {
    detailAsset = asset;
    selectedRefIndex = 0;
  }

  function closeAssetDetail() {
    detailAsset = null;
    selectedRefIndex = 0;
  }
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
        <button class="asset-card asset-card-button" on:click={() => openAssetDetail(asset)}>
          <div class={'asset-preview ' + getAssetPreviewClass(asset)}>
            {#if asset.image}
              <img class="asset-image" src={asset.image} alt={asset.name} />
            {:else if asset.type !== 'scene'}
              <div class="portrait">{asset.initial}</div>
            {/if}
            {#if getAssetReferences(asset).length > 1}
              <div class="asset-ref-badge">{getAssetReferences(asset).length} 张</div>
            {/if}
          </div>

          <div class="asset-body">
            <div class="asset-name">{asset.name}</div>
            <div class="asset-desc">{asset.description}</div>
          </div>
          <div class="project-card-actions">
            <span
              class="project-action-btn project-action-danger"
              role="button"
              tabindex="0"
              aria-label={`删除 ${asset.name}`}
              on:click|stopPropagation={() => dispatch('deleteAsset', asset)}
              on:keydown|stopPropagation={(e) => e.key === 'Enter' && dispatch('deleteAsset', asset)}
            >删除</span>
          </div>
        </button>
      {/each}

      <button class="empty-card" on:click={createAsset}>
        <div><b>新增素材</b><span>上传参考图，或根据剧情创建角色和场景。</span></div>
      </button>
    </div>
  </div>
</div>

{#if detailAsset}
  <div class="modal-backdrop" role="presentation">
    <div class="modal-panel asset-detail-modal" role="dialog" aria-modal="true" aria-labelledby="asset-detail-title">
      <div class="modal-head">
        <div>
          <div class="modal-title-accent" id="asset-detail-title">{detailAsset.name}</div>
          <div class="panel-subtitle">{getAssetTypeLabel(detailAsset.type)} · {detailRefs.length} 张参考 · {detailAsset.updated_at}</div>
        </div>
        <button class="modal-close" aria-label="关闭" on:click={closeAssetDetail}>×</button>
      </div>

      <div class="modal-body asset-detail-body">
        <div class="asset-detail-media">
          <div class={'asset-detail-stage ' + getAssetPreviewClass(detailAsset)}>
            {#if selectedRef?.url}
              <img class="asset-detail-image" src={selectedRef.url} alt={selectedRef.name} />
            {:else}
              <div class="asset-detail-placeholder">
                <div class="portrait">{detailAsset.initial}</div>
                <span>{selectedRef?.name || detailAsset.name}</span>
              </div>
            {/if}
          </div>

          <div class="asset-ref-strip" aria-label="素材参考列表">
            {#each detailRefs as reference, index}
              <button class:active={index === selectedRefIndex} on:click={() => (selectedRefIndex = index)}>
                {#if reference.url}
                  <img src={reference.url} alt={reference.name} />
                {:else}
                  <span>{String(index + 1).padStart(2, '0')}</span>
                {/if}
              </button>
            {/each}
          </div>
        </div>

        <div class="preview-detail asset-detail-info">
          <div class="preview-detail-head">
            <b>{selectedRef?.name || '素材详情'}</b>
            <span>{selectedRef?.type || detailAsset.type}</span>
          </div>
          <div class="preview-row"><span>素材描述</span><p>{detailAsset.description}</p></div>
          {#if selectedRef?.note}<div class="preview-row"><span>参考说明</span><p>{selectedRef.note}</p></div>{/if}
          <div class="preview-row"><span>资产类型</span><p>{getAssetTypeLabel(detailAsset.type)}</p></div>
          <div class="preview-row"><span>参考数量</span><p>{detailRefs.length} 张</p></div>
        </div>
      </div>
    </div>
  </div>
{/if}
