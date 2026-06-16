import { Image } from '@tarojs/components'
import { localIconAssets, type IconTone } from '@/assets/icons'

export type IconName =
  | 'ai'
  | 'bot'
  | 'back'
  | 'ball'
  | 'calendar'
  | 'chart'
  | 'chevron'
  | 'clock'
  | 'defense'
  | 'group'
  | 'info'
  | 'medal'
  | 'plus'
  | 'refresh'
  | 'share'
  | 'shield'
  | 'spark'
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
  return localIconAssets[name]?.[tone] || localIconAssets.info[tone]
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
