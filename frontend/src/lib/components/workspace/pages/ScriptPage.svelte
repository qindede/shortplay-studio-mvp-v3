<script lang="ts">
  import type { Asset, Episode, Project, Shot, VideoVersion } from '$lib/api';
  import { getStatusClass, getStatusLabel, type PageKey } from '$lib/workspace/ui';

  export let selectedEpisode: Episode | null = null;
  export let currentProject: Project | null = null;
  export let shots: Shot[] = [];
  export let versions: VideoVersion[] = [];
  export let assets: Asset[] = [];
  export let episodeTitle = '';
  export let episodeSummary = '';
  export let episodeScript = '';
  export let episodeDuration = 30;
  export let setPage: (page: PageKey) => void | Promise<void>;
  export let saveEpisodeOnly: () => void | Promise<void>;
  export let saveAndGenerateStoryboard: () => void | Promise<void>;
  export let batchGenerateVideos: () => void | Promise<void>;

  $: characterNames =
    assets
      .filter((asset) => asset.type === 'character')
      .slice(0, 3)
      .map((asset) => asset.name.replace(/.*：/, ''))
      .join('、') || '未配置';
  $: sceneName = assets.find((asset) => asset.type === 'scene')?.name || '未配置';
</script>

{#if selectedEpisode}
  <div class="workspace-layout">
    <div>
      <div class="panel script-editor">
        <div class="panel-head">
          <div>
            <div class="panel-title">本集脚本</div>
            <div class="panel-subtitle">先打磨情绪曲线，再生成可以直接进入视频生产的镜头表。</div>
          </div>
          <button class="btn btn-secondary" on:click={saveEpisodeOnly}>保存草稿</button>
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
            <div class="tag-list">
              <span class="tag">身份反转</span>
              <span class="tag">订婚现场</span>
              <span class="tag">当众打脸</span>
              <span class="tag">强情绪冲突</span>
            </div>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-head">
          <div>
            <div class="panel-title">镜头表</div>
            <div class="panel-subtitle">每个镜头都可以独立进入视频生成，并保留状态回看。</div>
          </div>
          <div class="panel-actions">
            <button class="btn btn-secondary" on:click={saveAndGenerateStoryboard}>生成 / 更新分镜</button>
            <button class="btn btn-primary" on:click={batchGenerateVideos}>批量生成视频</button>
          </div>
        </div>

        <div class="panel-body table-wrap">
          <table class="table">
            <thead><tr><th>镜头</th><th>画面</th><th>台词 / 旁白</th><th>角色 / 场景</th><th>时长</th><th>状态</th></tr></thead>
            <tbody>
              {#each shots as shot}
                <tr>
                  <td>#{String(shot.no).padStart(2, '0')}</td>
                  <td><div class="main-text">{shot.title}</div><div class="sub-text">{shot.visual}</div></td>
                  <td>{shot.dialogue || '无台词'}</td>
                  <td>{shot.characters.join('、')} / {shot.scene}</td>
                  <td>{shot.duration}s</td>
                  <td><span class={'status ' + getStatusClass(shot.status)}>{getStatusLabel(shot.status)}</span></td>
                </tr>
              {:else}
                <tr><td colspan="6"><div class="sub-text">暂无分镜。点击“生成 / 更新分镜”后，镜头表会出现在这里。</div></td></tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div>
      <div class="export-card">
        <div class="title">本集概览</div>
        <div class="export-row"><span>所属项目</span><b>{currentProject?.short_name}</b></div>
        <div class="export-row"><span>当前剧集</span><b>第 {String(selectedEpisode.no).padStart(2, '0')} 集</b></div>
        <div class="export-row"><span>镜头数量</span><b>{shots.length} 镜头</b></div>
        <div class="export-row"><span>成片版本</span><b>{versions.length} 个</b></div>
        <div class="export-row"><span>预计时长</span><b>{episodeDuration}s</b></div>
      </div>

      <div class="panel companion-panel">
        <div class="panel-head">
          <div>
            <div class="panel-title">本集素材</div>
            <div class="panel-subtitle">从项目素材库复用角色和场景。</div>
          </div>
        </div>

        <div class="panel-body">
          <div class="info-card"><div class="label">角色</div><div class="value">{characterNames}</div></div>
          <div class="info-card"><div class="label">场景</div><div class="value">{sceneName}</div></div>
          <button class="btn btn-secondary full-width" on:click={() => setPage('assets')}>管理素材</button>
        </div>
      </div>
    </div>
  </div>
{:else}
  <div class="empty-card page-empty"><div><b>还没有选中剧集</b><span>请先在剧集编排中选择或新建一集。</span></div></div>
{/if}
