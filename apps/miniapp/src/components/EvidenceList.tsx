import { Text, View } from '@tarojs/components'
import type { Evidence } from '@/services/mock'

export function EvidenceList({ items }: { items: Evidence[] }) {
  return (
    <View className='evidence-list'>
      {items.map(item => (
        <View className='evidence-row' key={item.label}>
          <View>
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

