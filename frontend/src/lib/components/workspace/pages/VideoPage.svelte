<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { Episode, Shot, VideoJob, VideoVersion } from '$lib/api';
  import { getStatusClass, getStatusLabel } from '$lib/workspace/ui';

  export let selectedEpisode: Episode | null = null;
  export let shots: Shot[] = [];
  export let videoJobs: VideoJob[] = [];
  export let versions: VideoVersion[] = [];
  export let composeVideo: () => void | Promise<void>;
  export let regenerateVideo: (shotId: string) => void | Promise<void>;

  const dispatch = createEventDispatcher<{ deleteVersion: VideoVersion }>();

  type PreviewTarget = {
    title: string;
    subtitle: string;
    description: string;
    duration: number;
    status: string;
    ratio: string;
    previewUrl: string;
    updatedAt: string;
    visual?: string;
    dialogue?: string;
    characters?: string;
    scene?: string;
  };

  let previewTarget: PreviewTarget | null = null;

  $: completedShots = shots.filter((shot) => shot.status === 'completed').length;

  function getVideoUrl(item: VideoJob | VideoVersion) {
    return item.preview_url || item.video_url || '';
  }

  function canPreviewTask(task: VideoJob) {
    return task.status === 'completed' || task.progress >= 100;
  }

  function findShot(task: VideoJob) {
    return shots.find((shot) => shot.id === task.shot_id);
  }

  function openTaskPreview(task: VideoJob) {
    if (!canPreviewTask(task)) return;

    const shot = findShot(task);
    previewTarget = {
      title: task.title,
      subtitle: shot ? `镜头 #${String(shot.no).padStart(2, '0')}` : '镜头片段',
      description: shot?.visual || '视频片段已生成，可在接入真实媒体地址后播放源文件。',
      duration: task.duration,
      status: task.status,
      ratio: '9:16',
      previewUrl: getVideoUrl(task),
      updatedAt: task.updated_at,
      visual: shot?.visual,
      dialogue: shot?.dialogue,
      characters: shot?.characters.join('、'),
      scene: shot?.scene
    };
  }

  function openVersionPreview(version: VideoVersion) {
    previewTarget = {
      title: version.name,
      subtitle: selectedEpisode ? `第 ${String(selectedEpisode.no).padStart(2, '0')} 集成片` : '成片版本',
      description: version.description,
      duration: version.duration,
      status: version.status,
      ratio: version.ratio,
      previewUrl: getVideoUrl(version),
      updatedAt: version.created_at
    };
  }

  function closePreview() {
    previewTarget = null;
  }
</script>

<div class="video-layout">
  <div>
    <div class="panel">
      <div class="panel-head">
        <div>
          <div class="panel-title">第 {String(selectedEpisode?.no || 0).padStart(2, '0')} 集视频任务</div>
          <div class="panel-subtitle">跟踪每个镜头片段的生成进度。</div>
        </div>
      </div>

      <div class="panel-body table-wrap">
        <table class="table">
          <thead><tr><th>任务</th><th>分镜号</th><th>时长</th><th>进度</th><th>状态</th><th>更新时间</th><th>操作</th></tr></thead>
          <tbody>
            {#each videoJobs as task}
              {@const shot = findShot(task)}
              <tr>
                <td><div class="main-text">{task.title}</div><div class="sub-text">{shot?.visual || '角色参考 + 场景参考'}</div></td>
                <td>{shot ? `分镜 #${String(shot.no).padStart(2, '0')}` : task.shot_id}</td>
                <td>{task.duration}s</td>
                <td><div class="progress"><span style={`width: ${task.progress}%`}></span></div></td>
                <td><span class={'status ' + getStatusClass(task.status)}>{getStatusLabel(task.status)}</span></td>
                <td>{task.updated_at}</td>
                <td>
                  <button class="btn btn-text" disabled={!canPreviewTask(task)} on:click={() => openTaskPreview(task)}>预览</button>
                  <button class="btn btn-text" on:click={() => regenerateVideo(task.shot_id)}>重新生成</button>
                </td>
              </tr>
            {:else}
              <tr><td colspan="7"><div class="sub-text">暂无视频任务。请先在“脚本与分镜”中生成分镜并批量生成视频。</div></td></tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>

    <div class="panel">
      <div class="panel-head">
        <div>
          <div class="panel-title">成片版本</div>
          <div class="panel-subtitle">为同一集保留不同开头、节奏和导出方案。</div>
        </div>
      </div>

      <div class="panel-body">
        <div class="video-grid">
          {#each versions as version}
            <button class="video-card video-card-button" on:click={() => openVersionPreview(version)}>
              <div class={'video-thumb ' + version.theme}><div class="play"></div></div>
              <div class="video-body"><div class="video-name">{version.name}</div><div class="video-desc">{version.description} / {version.ratio}</div></div>
              <div class="project-card-actions">
                <span
                  class="project-action-btn project-action-danger"
                  role="button"
                  tabindex="0"
                  aria-label={`删除 ${version.name}`}
                  on:click|stopPropagation={() => dispatch('deleteVersion', version)}
                  on:keydown|stopPropagation={(e) => e.key === 'Enter' && dispatch('deleteVersion', version)}
                >删除</span>
              </div>
            </button>
          {:else}
            <div class="empty-card"><div><b>暂无成片版本</b><span>合成后会在这里展示不同版本。</span></div></div>
          {/each}
        </div>
      </div>
    </div>
  </div>

  <div>
    <div class="export-card">
      <div class="title">本集导出</div>
      <div class="export-row"><span>当前剧集</span><b>第 {String(selectedEpisode?.no || 0).padStart(2, '0')} 集</b></div>
      <div class="export-row"><span>视频比例</span><b>9:16</b></div>
      <div class="export-row"><span>清晰度</span><b>1080P</b></div>
      <div class="export-row"><span>字幕样式</span><b>白字黑边</b></div>
      <div class="export-row"><span>镜头状态</span><b>{completedShots}/{shots.length} 完成</b></div>
      <button class="btn btn-blue full-width export-action" on:click={composeVideo}>合成本集视频</button>
    </div>
  </div>
</div>

{#if previewTarget}
  <div class="modal-backdrop" role="presentation">
    <div class="modal-panel video-preview-modal" role="dialog" aria-modal="true" aria-labelledby="video-preview-title">
      <div class="modal-head">
        <div>
          <div class="modal-title-accent" id="video-preview-title">视频预览</div>
          <div class="panel-subtitle">{previewTarget.subtitle} · {previewTarget.duration}s · {previewTarget.ratio}</div>
        </div>
        <button class="modal-close" aria-label="关闭" on:click={closePreview}>×</button>
      </div>

      <div class="modal-body video-preview-body">
        <div class="preview-stage">
          {#if previewTarget.previewUrl}
            <!-- svelte-ignore a11y_media_has_caption -->
            <video class="preview-video" src={previewTarget.previewUrl} controls autoplay playsinline></video>
          {:else}
            <div class="preview-placeholder">
              <div class="preview-status">{getStatusLabel(previewTarget.status)}</div>
              <div class="preview-play"><div class="play"></div></div>
              <div class="preview-caption">
                <b>{previewTarget.title}</b>
                <span>{previewTarget.description}</span>
              </div>
            </div>
          {/if}
        </div>

        <div class="preview-detail">
          <div class="preview-detail-head">
            <b>{previewTarget.title}</b>
            <span>{previewTarget.updatedAt}</span>
          </div>
          {#if previewTarget.visual}<div class="preview-row"><span>画面</span><p>{previewTarget.visual}</p></div>{/if}
          {#if previewTarget.dialogue}<div class="preview-row"><span>台词 / 旁白</span><p>{previewTarget.dialogue}</p></div>{/if}
          {#if previewTarget.characters}<div class="preview-row"><span>人物角色</span><p>{previewTarget.characters}</p></div>{/if}
          {#if previewTarget.scene}<div class="preview-row"><span>场景</span><p>{previewTarget.scene}</p></div>{/if}
        </div>
      </div>
      
    </div>
  </div>
{/if}
