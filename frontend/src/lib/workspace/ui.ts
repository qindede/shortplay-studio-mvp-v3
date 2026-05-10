import type { Status } from '$lib/api';

export type AuthMode = 'login' | 'register';
export type PageKey = 'projects' | 'episodes' | 'script' | 'assets' | 'video' | 'account' | 'password';

interface PageMeta {
  title: string;
  description: string;
  actionLabel: string;
}

export const pageMeta: Record<PageKey, PageMeta> = {
  projects: {
    title: '项目中心',
    description: '从项目、剧集、素材到成片，掌控整条短剧生产线',
    actionLabel: '新建项目'
  },
  episodes: {
    title: '剧集编排',
    description: '把故事拆成连续节奏，快速推进每一集的制作状态',
    actionLabel: '新建剧集'
  },
  script: {
    title: '脚本与分镜',
    description: '编辑剧情、生成镜头，让文本进入可拍摄状态',
    actionLabel: '生成分镜'
  },
  assets: {
    title: '角色与场景库',
    description: '沉淀可复用的角色、场景、图片和声音资产',
    actionLabel: '新建素材'
  },
  video: {
    title: '视频中心台',
    description: '查看片段生成、版本合成和竖屏导出状态',
    actionLabel: '合成视频'
  },
  account: {
    title: '额度与账户',
    description: '查看积分、生成额度和最近的消耗流水',
    actionLabel: '购买额度'
  },
  password: {
    title: '密码安全',
    description: '修改当前账号的登录密码',
    actionLabel: '修改密码'
  }
};

const statusLabels: Record<Status, string> = {
  active: '制作中',
  review: '待审核',
  draft: '草稿',
  completed: '已完成',
  storyboard_ready: '分镜就绪',
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
