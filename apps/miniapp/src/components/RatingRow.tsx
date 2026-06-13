import { Text, View } from '@tarojs/components'

export function RatingRow({ label, value }: { label: string; value: number }) {
  return (
    <View className='rating-row'>
      <Text className='rating-row__label'>{label}</Text>
      <View className='rating-row__track'>
        <View className='rating-row__bar' style={{ width: `${value * 10}%` }} />
      </View>
      <Text className='rating-row__value'>{value.toFixed(1)}</Text>
    </View>
  )
}

