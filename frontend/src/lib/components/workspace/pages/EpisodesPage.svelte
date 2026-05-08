<script lang="ts">
  import type { Episode } from '$lib/api';
  import { getStatusClass, getStatusLabel } from '$lib/workspace/ui';

  export let episodes: Episode[] = [];
  export let selectedEpisode: Episode | null = null;
  export let selectEpisode: (episode: Episode, goScript?: boolean) => void | Promise<void>;
  export let createEpisode: () => void | Promise<void>;
</script>

<div class="episode-board">
  <div class="panel rail-panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">剧集目录</div>
        <div class="panel-subtitle">共 {episodes.length} 集</div>
      </div>
    </div>

    <div class="panel-body">
      <div class="episode-list">
        {#each episodes as episode}
          <button class:active={selectedEpisode?.id === episode.id} class="episode-item" on:click={() => selectEpisode(episode, true)}>
            <div class="episode-no">{String(episode.no).padStart(2, '0')}</div>
            <div class="episode-text">
              <div class="episode-title">{episode.title}</div>
              <div class="episode-sub">{episode.shot_count} 镜头 · {episode.version_count} 版本 · {getStatusLabel(episode.status)}</div>
            </div>
          </button>
        {/each}

        <button class="empty-card compact-empty" on:click={createEpisode}>
          <div><b>新增剧集</b><span>继续扩展当前短剧项目。</span></div>
        </button>
      </div>
    </div>
  </div>

  <div class="panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">制作清单</div>
        <div class="panel-subtitle">查看每一集的剧情、镜头数量、版本数量和制作状态。</div>
      </div>
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
              <td><button class="btn btn-text" on:click={() => selectEpisode(episode, true)}>编辑</button></td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>
</div>
