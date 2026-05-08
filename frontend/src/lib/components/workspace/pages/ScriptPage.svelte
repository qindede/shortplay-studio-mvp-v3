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
      <div class="panel">
        <div class="panel-head">
          <div>
            <div class="panel-title">本集剧情</div>
            <div class="panel-subtitle">修改剧情后可重新拆分镜，也可只保存草稿。</div>
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
            <div class="panel-title">本集分镜</div>
            <div class="panel-subtitle">每个镜头可单独生成、替换、重生成。</div>
          </div>
          <div>
            <button class="btn btn-secondary" on:click={saveAndGenerateStoryboard}>生成/更新分镜</button>
            <button class="btn btn-primary" on:click={batchGenerateVideos}>批量生成视频</button>
          </div>
        </div>

        <div class="panel-body table-wrap">
          <table class="table">
            <thead><tr><th>镜头</th><th>画面描述</th><th>台词/旁白</th><th>角色/场景</th><th>时长</th><th>状态</th></tr></thead>
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
                <tr><td colspan="6"><div class="sub-text">暂无分镜，点击「生成/更新分镜」。</div></td></tr>
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
        <div class="export-row"><span>当前剧集</span><b>第{String(selectedEpisode.no).padStart(2, '0')}集</b></div>
        <div class="export-row"><span>分镜数量</span><b>{shots.length}镜头</b></div>
        <div class="export-row"><span>成片版本</span><b>{versions.length}个</b></div>
        <div class="export-row"><span>预计时长</span><b>{episodeDuration}s</b></div>
      </div>

      <div class="panel" style="margin-top:16px;">
        <div class="panel-head">
          <div>
            <div class="panel-title">本集素材</div>
            <div class="panel-subtitle">从项目素材库选择。</div>
          </div>
        </div>

        <div class="panel-body">
          <div class="info-card"><div class="label">角色</div><div class="value">{characterNames}</div></div>
          <div class="info-card"><div class="label">场景</div><div class="value">{sceneName}</div></div>
          <button class="btn btn-secondary" style="width:100%;" on:click={() => setPage('assets')}>管理素材</button>
        </div>
      </div>
    </div>
  </div>
{/if}
