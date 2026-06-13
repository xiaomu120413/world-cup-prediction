import { Text, View } from '@tarojs/components'

type Props = {
  label: string
  value: number
  meta?: string
}

export function ProgressRow({ label, value, meta }: Props) {
  return (
    <View className='progress-row'>
      <View className='progress-row__top'>
        <Text className='progress-row__label'>{label}</Text>
        <Text className='progress-row__value'>{value}%</Text>
      </View>
      <View className='progress-row__track'>
        <View className='progress-row__bar' style={{ width: `${value}%` }} />
      </View>
      {meta ? <Text className='progress-row__meta'>{meta}</Text> : null}
    </View>
  )
}

