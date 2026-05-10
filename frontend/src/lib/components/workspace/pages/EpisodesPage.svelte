<script lang="ts">
  import type { Episode } from '$lib/api';
  import { getStatusClass, getStatusLabel } from '$lib/workspace/ui';

  export let episodes: Episode[] = [];
  export let selectEpisode: (episode: Episode, goScript?: boolean) => void | Promise<void>;
  export let createEpisode: () => void | Promise<void>;
</script>

<div class="episode-board">
  <div class="panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">剧集目录</div>
        <div class="panel-subtitle">共 {episodes.length} 集。选择一集进入脚本分镜。</div>
      </div>
      <button class="btn btn-primary" on:click={createEpisode}>新增剧集</button>
    </div>

    <div class="panel-body table-wrap">
      <table class="table">
        <thead><tr><th>剧集</th><th>剧情摘要</th><th>分镜</th><th>版本</th><th>时长</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>
          {#each episodes as episode}
            <tr>
              <td><div class="main-text">第 {String(episode.no).padStart(2, '0')} 集 · {episode.title}</div></td>
              <td><div class="sub-text">{episode.summary}</div></td>
              <td>{episode.shot_count} 镜头</td>
              <td>{episode.version_count} 个</td>
              <td>{episode.duration_target}s</td>
              <td><span class={'status ' + getStatusClass(episode.status)}>{getStatusLabel(episode.status)}</span></td>
              <td><button class="btn btn-text" on:click={() => selectEpisode(episode, true)}>剧集编辑</button></td>
            </tr>
          {:else}
            <tr>
              <td colspan="7"><div class="sub-text">暂无剧集。点击“新增剧集”开始编排。</div></td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>
</div>
