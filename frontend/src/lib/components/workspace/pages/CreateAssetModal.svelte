<script lang="ts">
  import type { Asset } from '$lib/api';
  import { api } from '$lib/api';
  import PromptOptimizeButton from '../PromptOptimizeButton.svelte';

  export let show = false;
  export let projectId: string;
  export let pointBalance = 0;
  export let onCreate: (asset: Asset) => void;
  export let onClose: () => void;

  $: aiCost = type === 'audio' ? 5 : 20;

  let mode: 'upload' | 'ai' = 'upload';
  let type: Asset['type'] = 'character';
  let name = '';
  let description = '';
  let voice = '';
  let voiceFile: File | null = null;
  let voicePreviewUrl: string | null = null;
  let files: File[] = [];
  let previewUrls: string[] = [];
  let mainIndex = 0;
  let aiPrompt = '';
  let generating = false;
  let submitting = false;
  let error = '';

  const typeOptions: { value: Asset['type']; label: string }[] = [
    { value: 'character', label: '角色' },
    { value: 'scene', label: '场景' },
    { value: 'image', label: '图片' },
    { value: 'audio', label: '声音' }
  ];

  function reset() {
    mode = 'upload';
    type = 'character';
    name = '';
    description = '';
    voice = '';
    voiceFile = null;
    voicePreviewUrl = null;
    files = [];
    previewUrls = [];
    mainIndex = 0;
    aiPrompt = '';
    generating = false;
    submitting = false;
    error = '';
  }

  function handleClose() {
    reset();
    onClose();
  }

  function handleFileSelect(e: Event) {
    const input = e.target as HTMLInputElement;
    if (!input.files?.length) return;
    addFiles(Array.from(input.files));
    input.value = '';
  }

  function addFiles(newFiles: File[]) {
    for (const f of newFiles) {
      files = [...files, f];
      const url = URL.createObjectURL(f);
      previewUrls = [...previewUrls, url];
    }
  }

  function removeFile(index: number) {
    URL.revokeObjectURL(previewUrls[index]);
    files = files.filter((_, i) => i !== index);
    previewUrls = previewUrls.filter((_, i) => i !== index);
    if (mainIndex >= files.length) mainIndex = Math.max(0, files.length - 1);
  }

  function setMain(index: number) {
    mainIndex = index;
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    const dropped = Array.from(e.dataTransfer?.files || []);
    if (dropped.length) addFiles(dropped);
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
  }

  function handleVoiceSelect(e: Event) {
    const input = e.target as HTMLInputElement;
    if (!input.files?.length) return;
    voiceFile = input.files[0];
    voicePreviewUrl = URL.createObjectURL(voiceFile);
    input.value = '';
  }

  function removeVoice() {
    if (voicePreviewUrl) URL.revokeObjectURL(voicePreviewUrl);
    voiceFile = null;
    voicePreviewUrl = null;
  }

  async function handleSubmit() {
    if (!name.trim()) { error = '请输入素材名称'; return; }
    error = '';

    if (mode === 'upload') {
      await submitUpload();
    } else {
      await submitAiGenerate();
    }
  }

  async function submitUpload() {
    submitting = true;
    try {
      let imageUrl: string | undefined;
      let voiceUrl: string | undefined;
      const refs: { type: string; name: string; url?: string }[] = [];

      for (let i = 0; i < files.length; i++) {
        const result = await api.upload(files[i]);
        const ref = { type: 'image', name: `参考 ${String(i + 1).padStart(2, '0')}`, url: result.url };
        refs.push(ref);
        if (i === mainIndex) imageUrl = result.url;
      }

      if (voiceFile) {
        const result = await api.upload(voiceFile);
        voiceUrl = result.url;
      }

      const asset = await api.createAsset(projectId, {
        type,
        name: name.trim(),
        description: description.trim(),
        initial: name.trim().slice(0, 1),
        image: imageUrl,
        voice: voice.trim() || undefined,
        voice_url: voiceUrl,
        references: refs.length ? refs : undefined
      });

      onCreate(asset);
      reset();
    } catch (e: any) {
      error = e.message || '上传失败';
    } finally {
      submitting = false;
    }
  }

  async function submitAiGenerate() {
    if (!aiPrompt.trim()) { error = '请输入生成描述'; return; }
    generating = true;
    error = '';
    try {
      const asset = await api.generateAsset(projectId, {
        type,
        name: name.trim(),
        description: description.trim(),
        prompt: aiPrompt.trim()
      });
      onCreate(asset);
      reset();
    } catch (e: any) {
      error = e.message || '生成失败';
    } finally {
      generating = false;
    }
  }
</script>

{#if show}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div class="modal-backdrop" role="presentation" on:click={handleClose}>
    <div class="modal-panel create-asset-modal" role="dialog" aria-modal="true" aria-labelledby="create-asset-title" tabindex="-1" on:click|stopPropagation>
      <div class="modal-head">
        <div>
          <div class="modal-title-accent" id="create-asset-title">新建素材</div>
          <div class="panel-subtitle">上传参考图或使用 AI 生成角色与场景素材。</div>
        </div>
        <button class="modal-close" aria-label="关闭" on:click={handleClose}>×</button>
      </div>

      <div class="modal-body create-asset-body">
        {#if error}<div class="error compact-alert">{error}</div>{/if}

        <div class="create-asset-tabs">
          <button class:active={mode === 'upload'} on:click={() => (mode = 'upload')}>手动上传</button>
          <button class:active={mode === 'ai'} on:click={() => (mode = 'ai')}>AI 生成</button>
        </div>

        <div class="field-grid">
          <div class="field">
            <label for="asset-type">素材类型</label>
            <select id="asset-type" bind:value={type}>
              {#each typeOptions as opt}
                <option value={opt.value}>{opt.label}</option>
              {/each}
            </select>
          </div>
          <div class="field">
            <label for="asset-name">素材名称</label>
            <input id="asset-name" bind:value={name} placeholder={type === 'scene' ? '如：宴会厅' : type === 'character' ? '如：林晚' : '素材名称'} />
          </div>
        </div>

        <div class="field">
          <label for="asset-desc">素材描述</label>
          <input id="asset-desc" bind:value={description} placeholder="简要描述素材的外观、特征或用途" />
        </div>

        {#if type === 'character'}
          <div class="field">
            <label for="asset-voice">声音特征</label>
            <input id="asset-voice" bind:value={voice} placeholder="如：温柔清冷女声、低沉磁性男声" />
          </div>
          {#if mode === 'upload'}
            <div class="field">
              <label>声音文件</label>
              {#if voiceFile}
                <div class="voice-file-row">
                  <span class="voice-file-name">{voiceFile.name}</span>
                  <button class="voice-file-remove" on:click={removeVoice}>×</button>
                </div>
              {:else}
                <button class="voice-upload-btn" on:click={() => document.getElementById('voice-file-input')?.click()}>
                  上传声音文件
                </button>
              {/if}
              <input
                id="voice-file-input"
                type="file"
                accept="audio/*"
                hidden
                on:change={handleVoiceSelect}
              />
            </div>
          {/if}
        {/if}

        {#if mode === 'upload'}
          <div
            class="upload-row"
            role="button"
            tabindex="0"
            on:drop={handleDrop}
            on:dragover={handleDragOver}
            on:click={(e) => {
              if ((e.target as HTMLElement).closest('.upload-thumb') || (e.target as HTMLElement).closest('.upload-add-card')) return;
              document.getElementById('asset-file-input')?.click();
            }}
            on:keydown={(e) => e.key === 'Enter' && document.getElementById('asset-file-input')?.click()}
          >
            <input
              id="asset-file-input"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              multiple
              hidden
              on:change={handleFileSelect}
            />
            <div
              class="upload-add-card"
              role="button"
              tabindex="0"
              on:click|stopPropagation={() => document.getElementById('asset-file-input')?.click()}
              on:keydown={(e) => e.key === 'Enter' && document.getElementById('asset-file-input')?.click()}
              on:drop|stopPropagation={handleDrop}
              on:dragover|stopPropagation={handleDragOver}
            >
              <span class="upload-add-icon">+</span>
              <span class="upload-add-text">{previewUrls.length === 0 ? '上传参考图' : '添加'}</span>
              <span class="upload-add-hint">JPG / PNG / WebP</span>
            </div>
            {#each previewUrls as url, i}
              <div class="upload-thumb" class:is-main={i === mainIndex} role="presentation" on:click|stopPropagation>
                <img src={url} alt="参考 {i + 1}" />
                <div class="upload-thumb-overlay">
                  <button class="thumb-btn" title="设为主图" on:click|stopPropagation={() => setMain(i)}>
                    {i === mainIndex ? '★' : '☆'}
                  </button>
                  <button class="thumb-btn thumb-btn-remove" title="删除" on:click|stopPropagation={() => removeFile(i)}>×</button>
                </div>
                {#if i === mainIndex}
                  <div class="thumb-main-label">主图</div>
                {/if}
              </div>
            {/each}
          </div>
        {:else}
          <div class="field">
            <label for="asset-ai-prompt">生成描述</label>
            <div class="prompt-field">
              <textarea
                id="asset-ai-prompt"
                bind:value={aiPrompt}
                placeholder={type === 'character'
                  ? '如：一个穿黑色西装的年轻男性，冷峻面容，短发，站在落地窗前'
                  : type === 'scene'
                    ? '如：现代风格的豪华宴会厅，水晶吊灯，金色装饰，舞池中央'
                    : '描述你想要生成的素材外观'}
              ></textarea>
              <PromptOptimizeButton
                value={aiPrompt}
                context={'asset_' + type}
                onOptimized={(v) => (aiPrompt = v)}
              />
            </div>
          </div>
        {/if}
      </div>

      <div class="modal-actions">
        {#if mode === 'ai' && pointBalance < aiCost}
          <div class="inline-hint warn">当前积分 {pointBalance}，不足以生成素材。</div>
        {/if}
        <button class="btn btn-secondary" on:click={handleClose}>取消</button>
        <button class="btn btn-primary" disabled={submitting || generating || (mode === 'ai' && pointBalance < aiCost)} on:click={handleSubmit}>
          {#if generating}
            生成中...
          {:else if submitting}
            创建中...
          {:else}
            {mode === 'ai' ? `生成并创建（ ${aiCost} 积分 ）` : '创建素材'}
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}
