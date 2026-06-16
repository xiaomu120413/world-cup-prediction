import { Image } from '@tarojs/components'
import { localIconAssets, type IconTone } from '@/assets/icons'

export type IconName =
  | 'ai'
  | 'appearance'
  | 'assist'
  | 'bot'
  | 'back'
  | 'ball'
  | 'calendar'
  | 'chart'
  | 'chevron'
  | 'clock'
  | 'defense'
  | 'euro'
  | 'fitness'
  | 'group'
  | 'info'
  | 'medal'
  | 'plus'
  | 'refresh'
  | 'share'
  | 'shield'
  | 'spark'
  | 'stadium'
  | 'star'
  | 'stability'
  | 'target'
  | 'team'
  | 'trend'
  | 'trophy'
  | 'warning'

const colorToneMap: Record<string, IconTone> = {
  '#2563eb': 'blue',
  '#64748b': 'slate',
  '#94a3b8': 'muted',
  '#0f172a': 'ink',
  '#ffffff': 'white',
  '#16a34a': 'green',
  '#dc2626': 'red',
  '#6b7280': 'gray',
  '#f59e0b': 'amber'
}

function iconUrl(name: IconName, color: string) {
  const tone = colorToneMap[color.toLowerCase()] || 'slate'
  if (name === 'bot') {
    return localIconAssets.ai[tone] || localIconAssets.ai.blue
  }
  if (name === 'trend') {
    return localIconAssets.chart[tone] || localIconAssets.chart.blue
  }
  if (name === 'warning') {
    return localIconAssets.shield[tone] || localIconAssets.shield.red
  }
  if (name === 'calendar' || name === 'plus') {
    return localIconAssets.info[tone] || localIconAssets.info.slate
  }
  return localIconAssets[name]?.[tone] || localIconAssets.info[tone] || localIconAssets.info.slate
}

export function Icon({
  name,
  color = '#64748b',
  size = 32,
  className = ''
}: {
  name: IconName
  color?: string
  size?: number
  className?: string
}) {
  return (
    <Image
      className={`icon icon--${size} ${className}`}
      src={iconUrl(name, color)}
      mode='aspectFit'
      style={{ width: `${size}rpx`, height: `${size}rpx`, minWidth: `${size}rpx`, minHeight: `${size}rpx` }}
    />
  )
}
