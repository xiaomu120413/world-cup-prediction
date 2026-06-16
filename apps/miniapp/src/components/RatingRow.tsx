import { Text, View } from '@tarojs/components'
import { Icon, type IconName } from '@/components/Icon'

function ratingIcon(label: string): IconName {
  if (label.includes('攻')) return 'target'
  if (label.includes('防')) return 'defense'
  if (label.includes('阵容')) return 'group'
  if (label.includes('稳定')) return 'stability'
  return 'chart'
}

export function RatingRow({ label, value }: { label: string; value: number }) {
  return (
    <View className='rating-row'>
      <View className='rating-row__icon'>
        <Icon name={ratingIcon(label)} color='#2563eb' size={34} />
      </View>
      <Text className='rating-row__label'>{label}</Text>
      <Text className='rating-row__value'>{value.toFixed(1)}</Text>
      <View className='rating-row__track'>
        <View className='rating-row__bar' style={{ width: `${value * 10}%` }} />
      </View>
    </View>
  )
}
