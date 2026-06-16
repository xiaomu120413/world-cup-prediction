import { Text, View } from '@tarojs/components'
import type { Evidence } from '@/services/mock'

export function EvidenceList({ items }: { items: Evidence[] }) {
  if (!items.length) {
    return <View className='empty-state'>关键证据待情报任务生成</View>
  }

  return (
    <View className='evidence-list'>
      {items.map(item => (
        <View className='evidence-row' key={item.label}>
          <View className={`evidence-row__marker ${item.value >= 0 ? 'evidence-row__marker--up' : 'evidence-row__marker--down'}`}>
            <Text>{item.value >= 0 ? '↑' : '↓'}</Text>
          </View>
          <View className='evidence-row__main'>
            <Text className='evidence-row__label'>{item.label}</Text>
            <Text className='evidence-row__note'>{item.note}</Text>
          </View>
          <Text className={`evidence-row__score ${item.value >= 0 ? 'text-positive' : 'text-negative'}`}>
            {item.value >= 0 ? '+' : ''}{item.value}
          </Text>
        </View>
      ))}
    </View>
  )
}
