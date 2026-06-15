import { Text, View } from '@tarojs/components'

type Props = {
  label: string
  value: number
  meta?: string
}

export function ProgressRow({ label, value, meta }: Props) {
  const width = Math.max(0, Math.min(value, 100))

  return (
    <View className='progress-row'>
      {label ? (
        <View className='progress-row__top'>
          <Text className='progress-row__label'>{label}</Text>
          <Text className='progress-row__value'>{value}%</Text>
        </View>
      ) : null}
      <View className='progress-row__track'>
        <View className='progress-row__bar' style={{ width: `${width}%` }} />
      </View>
      {meta ? <Text className='progress-row__meta'>{meta}</Text> : null}
    </View>
  )
}
