<script lang="ts">
  import type { Episode, Shot, VideoTask, VideoVersion } from '$lib/api';
  import { getStatusClass, getStatusLabel } from '$lib/workspace/ui';

  export let selectedEpisode: Episode | null = null;
  export let shots: Shot[] = [];
  export let videoTasks: VideoTask[] = [];
  export let versions: VideoVersion[] = [];
  export let composeVideo: () => void | Promise<void>;

  $: completedShots = shots.filter((shot) => shot.status === 'completed').length;
</script>

<div class="video-layout">
  <div>
    <div class="panel">
      <div class="panel-head">
        <div>
          <div class="panel-title">第{String(selectedEpisode?.no || 0).padStart(2, '0')}集视频任务</div>
          <div class="panel-subtitle">分镜视频片段生成状态。</div>
        </div>
      </div>

      <div class="panel-body table-wrap">
        <table class="table">
          <thead><tr><th>任务</th><th>镜头</th><th>时长</th><th>进度</th><th>状态</th><th>更新时间</th></tr></thead>
          <tbody>
            {#each videoTasks as task}
              <tr>
                <td><div class="main-text">{task.title}</div><div class="sub-text">角色参考 + 场景参考</div></td>
                <td>{task.shot_id}</td>
                <td>{task.duration}s</td>
                <td><div class="progress"><span style={`width: ${task.progress}%`}></span></div></td>
                <td><span class={'status ' + getStatusClass(task.status)}>{getStatusLabel(task.status)}</span></td>
                <td>{task.updated_at}</td>
              </tr>
            {:else}
              <tr><td colspan="6"><div class="sub-text">暂无视频任务，请先在「剧情与分镜」生成分镜并批量生成视频。</div></td></tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>

    <div class="panel">
      <div class="panel-head">
        <div>
          <div class="panel-title">成片版本</div>
          <div class="panel-subtitle">同一剧集可保留多个开头和节奏版本。</div>
        </div>
      </div>

      <div class="panel-body">
        <div class="video-grid">
          {#each versions as version}
            <div class="video-card">
              <div class={'video-thumb ' + version.theme}><div class="play"></div></div>
              <div class="video-body"><div class="video-name">{version.name}</div><div class="video-desc">{version.description} / {version.ratio}</div></div>
            </div>
          {/each}
        </div>
      </div>
    </div>
  </div>

  <div>
    <div class="export-card">
      <div class="title">本集导出</div>
      <div class="export-row"><span>当前剧集</span><b>第{String(selectedEpisode?.no || 0).padStart(2, '0')}集</b></div>
      <div class="export-row"><span>视频比例</span><b>9:16</b></div>
      <div class="export-row"><span>清晰度</span><b>1080P</b></div>
      <div class="export-row"><span>字幕样式</span><b>白字黑边</b></div>
      <div class="export-row"><span>镜头状态</span><b>{completedShots}/{shots.length}完成</b></div>
      <button class="btn btn-blue" style="width:100%; margin-top:14px;" on:click={composeVideo}>合成本集视频</button>
    </div>
  </div>
</div>
