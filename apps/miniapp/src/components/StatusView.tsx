import { Text, View } from '@tarojs/components'

export function StatusView({ title, detail }: { title: string; detail: string }) {
  return (
    <View className='status-view'>
      <Text className='status-view__title'>{title}</Text>
      <Text className='status-view__detail'>{detail}</Text>
    </View>
  )
}

