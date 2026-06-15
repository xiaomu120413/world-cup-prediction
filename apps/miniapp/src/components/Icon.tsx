import { Image } from '@tarojs/components'

type IconName =
  | 'ai'
  | 'back'
  | 'ball'
  | 'chart'
  | 'chevron'
  | 'clock'
  | 'medal'
  | 'refresh'
  | 'share'
  | 'shield'
  | 'spark'
  | 'star'
  | 'team'
  | 'trophy'

const iconMap: Record<IconName, string> = {
  ai: 'solar:stars-line-duotone',
  back: 'solar:alt-arrow-left-outline',
  ball: 'solar:football-outline',
  chart: 'solar:chart-2-outline',
  chevron: 'solar:alt-arrow-right-outline',
  clock: 'solar:clock-circle-outline',
  medal: 'solar:medal-ribbon-star-outline',
  refresh: 'solar:refresh-outline',
  share: 'solar:share-outline',
  shield: 'solar:shield-star-outline',
  spark: 'solar:magic-stick-3-outline',
  star: 'solar:star-outline',
  team: 'solar:users-group-rounded-outline',
  trophy: 'solar:cup-star-outline'
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
  const src = `https://api.iconify.design/${iconMap[name]}.svg?color=${encodeURIComponent(color)}`

  return (
    <Image
      className={`icon icon--${size} ${className}`}
      src={src}
      mode='aspectFit'
    />
  )
}
