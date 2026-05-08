import type { Status } from '$lib/api';

export type AuthMode = 'login' | 'register';
export type PageKey = 'projects' | 'episodes' | 'script' | 'assets' | 'video' | 'account';

interface PageMeta {
  title: string;
  description: string;
  actionLabel: string;
}

export const pageMeta: Record<PageKey, PageMeta> = {
  projects: {
    title: '项目中心',
    description: '管理短剧项目、剧集、素材和视频版本',
    actionLabel: '新建项目'
  },
  episodes: {
    title: '剧集管理',
    description: '当前项目下的多集内容',
    actionLabel: '新建剧集'
  },
  script: {
    title: '剧情与分镜',
    description: '编辑剧情并逐镜头生成视频',
    actionLabel: '保存并生成'
  },
  assets: {
    title: '素材库',
    description: '项目素材可被所有剧集复用',
    actionLabel: '新建素材'
  },
  video: {
    title: '视频中心',
    description: '查看任务、片段和成片版本',
    actionLabel: '合成视频'
  },
  account: {
    title: '额度与导出',
    description: '团队额度与默认导出设置',
    actionLabel: '购买额度'
  }
};

const statusLabels: Record<Status, string> = {
  active: '制作中',
  review: '待审核',
  draft: '草稿',
  completed: '已完成',
  storyboard_ready: '已生成',
  generating: '生成中',
  pending: '待生成',
  needs_review: '待优化',
  exported: '已导出'
};

export function getStatusClass(status: string) {
  if (['active', 'completed', 'storyboard_ready', 'exported'].includes(status)) return 'green';
  if (['generating', 'review'].includes(status)) return 'blue';
  if (['draft', 'pending'].includes(status)) return 'amber';
  if (['needs_review'].includes(status)) return 'purple';
  return 'gray';
}

export function getStatusLabel(status: string) {
  return statusLabels[status as Status] || status;
}

export function getUsagePercent(used: number, total: number) {
  if (total <= 0) return 0;
  return Math.round((used / total) * 100);
}
