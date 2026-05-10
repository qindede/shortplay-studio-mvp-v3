<script lang="ts">
  import type { Asset, Episode, Project, Shot, ShotPayload, ShotUpdate, VideoVersion } from '$lib/api';
  import { getStatusClass, getStatusLabel } from '$lib/workspace/ui';

  export let selectedEpisode: Episode | null = null;
  export let currentProject: Project | null = null;
  export let shots: Shot[] = [];
  export let versions: VideoVersion[] = [];
  export let assets: Asset[] = [];
  export let episodeTitle = '';
  export let episodeSummary = '';
  export let episodeScript = '';
  export let episodeDuration = 30;
  export let saveEpisodeOnly: () => void | Promise<void>;
  export let saveAndGenerateStoryboard: () => void | Promise<void>;
  export let generateVideoForShot: (shot: Shot) => void | Promise<void>;
  export let createShot: (payload: ShotPayload) => void | Promise<void>;
  export let updateShot: (shotId: string, payload: ShotUpdate) => void | Promise<void>;
  export let deleteShot: (shot: Shot) => void | Promise<void>;

  let shotEditorOpen = false;
  let shotEditorMode: 'create' | 'edit' = 'edit';
  let editingShot: Shot | null = null;
  let editTitle = '';
  let editVisual = '';
  let editDialogue = '';
  let editCharacters = '';
  let editScene = '';
  let editDuration = 1;
  let shotSaving = false;

  $: characterNames =
    assets
      .filter((asset) => asset.type === 'character')
      .slice(0, 3)
      .map((asset) => asset.name.replace(/.*：/, ''))
      .join('、') || '未配置';
  $: sceneName = assets.find((asset) => asset.type === 'scene')?.name || '未配置';

  function openShotCreator() {
    shotEditorOpen = true;
    shotEditorMode = 'create';
    editingShot = null;
    editTitle = '';
    editVisual = '';
    editDialogue = '';
    editCharacters = characterNames === '未配置' ? '' : characterNames;
    editScene = sceneName === '未配置' ? '' : sceneName;
    editDuration = 3;
  }

  function openShotEditor(shot: Shot) {
    shotEditorOpen = true;
    shotEditorMode = 'edit';
    editingShot = shot;
    editTitle = shot.title;
    editVisual = shot.visual;
    editDialogue = shot.dialogue;
    editCharacters = shot.characters.join('、');
    editScene = shot.scene;
    editDuration = shot.duration;
  }

  function closeShotEditor() {
    shotEditorOpen = false;
    editingShot = null;
  }

  function parseCharacters(value: string) {
    return value
      .split(/[、,\n]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  async function saveShotEdit() {
    if (!shotEditorOpen || shotSaving) return;

    const payload = {
      title: editTitle.trim() || '未命名分镜',
      visual: editVisual.trim(),
      dialogue: editDialogue.trim(),
      characters: parseCharacters(editCharacters),
      scene: editScene.trim(),
      duration: Math.max(1, Number(editDuration) || 1)
    };

    shotSaving = true;
    try {
      if (shotEditorMode === 'create') {
        await createShot(payload);
      } else if (editingShot) {
        await updateShot(editingShot.id, payload);
      }
      closeShotEditor();
    } finally {
      shotSaving = false;
    }
  }
</script>

{#if selectedEpisode}
  <div class="workspace-layout script-layout">
    <div class="script-left-column">
      <div class="panel shot-table-panel">
        <div class="panel-head">
          <div>
            <div class="panel-title">镜头表</div>
            <div class="panel-subtitle">每个镜头都可以独立进入视频生成，并保留状态回看。</div>
          </div>
          <div class="panel-actions">
            <button class="btn btn-secondary" on:click={openShotCreator}>新增分镜</button>
            <!-- <button class="btn btn-primary" on:click={batchGenerateVideos}>批量生成视频</button> -->
          </div>
        </div>

        <div class="panel-body table-wrap">
          <table class="table">
            <thead><tr><th>镜头</th><th>画面</th><th>台词 / 旁白</th><th>角色 / 场景</th><th>时长</th><th>状态</th><th>操作</th></tr></thead>
            <tbody>
              {#each shots as shot}
                <tr>
                  <td>#{String(shot.no).padStart(2, '0')}</td>
                  <td><div class="main-text">{shot.title}</div><div class="sub-text">{shot.visual}</div></td>
                  <td>{shot.dialogue || '无台词'}</td>
                  <td>{shot.characters.join('、')} / {shot.scene}</td>
                  <td>{shot.duration}s</td>
                  <td><span class={'status ' + getStatusClass(shot.status)}>{getStatusLabel(shot.status)}</span></td>
                  <td>
                    <div class="table-actions">
                      <button class="btn btn-text" on:click={() => openShotEditor(shot)}>修改</button>
                      <button class="btn btn-text" on:click={() => generateVideoForShot(shot)}>生成视频</button>
                      <button class="btn btn-text btn-danger" on:click={() => deleteShot(shot)}>删除</button>
                    </div>
                  </td>
                </tr>
              {:else}
                <tr><td colspan="7"><div class="sub-text">暂无分镜。可以新增单条分镜，或在右侧“本集脚本”中智能生成整集分镜。</div></td></tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="script-right-column">
      <div class="panel script-editor">
        <div class="panel-head">
          <div>
            <div class="panel-title">本集脚本</div>
            <div class="panel-subtitle">先打磨情绪曲线，再生成可以直接进入视频生产的镜头表。</div>
          </div>
        </div>

        <div class="panel-body">
          <div class="field-grid">
            <div class="field"><label for="episode-title">剧集标题</label><input id="episode-title" bind:value={episodeTitle} /></div>
            <div class="field"><label for="episode-duration">目标时长</label><input id="episode-duration" type="number" bind:value={episodeDuration} /></div>
          </div>
          <div class="field"><label for="episode-summary">剧情摘要</label><input id="episode-summary" bind:value={episodeSummary} /></div>
          <div class="field">
            <label for="episode-script">剧情内容</label>
            <textarea id="episode-script" bind:value={episodeScript}></textarea>
          </div>
          <div class="panel-actions script-editor-actions">
            <button class="btn btn-secondary" on:click={saveEpisodeOnly}>保存</button>
            <button class="btn btn-primary" on:click={saveAndGenerateStoryboard}>智能生成 / 更新分镜（10积分）</button>
          </div>
        </div>
      </div>

      <div class="export-card">
        <div class="title">本集概览</div>
        <div class="export-row"><span>所属项目</span><b>{currentProject?.short_name}</b></div>
        <div class="export-row"><span>当前剧集</span><b>第 {String(selectedEpisode.no).padStart(2, '0')} 集</b></div>
        <div class="export-row"><span>镜头数量</span><b>{shots.length} 镜头</b></div>
        <div class="export-row"><span>成片版本</span><b>{versions.length} 个</b></div>
        <div class="export-row"><span>预计时长</span><b>{episodeDuration}s</b></div>
      </div>
    </div>

    {#if shotEditorOpen}
      <div class="modal-backdrop">
        <div class="modal-panel shot-edit-modal">
          <div class="modal-head">
            <div>
              <div class="modal-title-accent">
                {shotEditorMode === 'create' ? '新增分镜' : `修改分镜 #${String(editingShot?.no || 0).padStart(2, '0')}`}
              </div>
              <div class="panel-subtitle">调整画面、台词、角色、场景和时长。</div>
            </div>
            <button class="modal-close" aria-label="关闭" on:click={closeShotEditor}>×</button>
          </div>

          <div class="modal-body">
            <div class="field-grid">
              <div class="field"><label for="shot-title">镜头标题</label><input id="shot-title" bind:value={editTitle} /></div>
              <div class="field"><label for="shot-duration">时长（秒）</label><input id="shot-duration" type="number" min="1" bind:value={editDuration} /></div>
            </div>
            <div class="field"><label for="shot-visual">画面描述</label><textarea id="shot-visual" class="compact-textarea" bind:value={editVisual}></textarea></div>
            <div class="field"><label for="shot-dialogue">台词 / 旁白</label><textarea id="shot-dialogue" class="compact-textarea" bind:value={editDialogue}></textarea></div>
            <div class="field-grid">
              <div class="field"><label for="shot-characters">角色</label><input id="shot-characters" bind:value={editCharacters} /></div>
              <div class="field"><label for="shot-scene">场景</label><input id="shot-scene" bind:value={editScene} /></div>
            </div>
          </div>

          <div class="modal-actions">
            <button class="btn btn-secondary" disabled={shotSaving} on:click={closeShotEditor}>取消</button>
            <button class="btn btn-primary" disabled={shotSaving} on:click={saveShotEdit}>
              {shotSaving ? '保存中...' : shotEditorMode === 'create' ? '新增分镜' : '保存更新'}
            </button>
          </div>
        </div>
      </div>
    {/if}
  </div>
{:else}
  <div class="empty-card page-empty"><div><b>还没有选中剧集</b><span>请先在剧集编排中选择或新建一集。</span></div></div>
{/if}
