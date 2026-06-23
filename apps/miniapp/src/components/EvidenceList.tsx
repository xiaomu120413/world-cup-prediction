import { Text, View } from '@tarojs/components'
import type { Evidence } from '@/services/types'

function evidenceTone(item: Evidence) {
  if (item.tone) return item.tone
  if (item.value > 0) return 'positive'
  if (item.value < 0) return 'negative'
  return 'neutral'
}

export function EvidenceList({ items }: { items: Evidence[] }) {
  if (!items.length) {
    return <View className='empty-state'>关键证据待情报任务生成</View>
  }

  return (
    <View className='evidence-list'>
      {items.map(item => {
        const tone = evidenceTone(item)
        return (
          <View className='evidence-row' key={item.label}>
            <View className={`evidence-row__marker evidence-row__marker--${tone}`}>
              <Text>{tone === 'positive' ? '+' : tone === 'negative' ? '-' : '0'}</Text>
            </View>
            <View className='evidence-row__main'>
              <Text className='evidence-row__label'>{item.label}</Text>
              <Text className='evidence-row__note'>{item.note}</Text>
            </View>
            <Text className={`evidence-row__score ${tone === 'positive' ? 'text-positive' : tone === 'negative' ? 'text-negative' : ''}`}>
              {item.displayValue ?? `${item.value >= 0 ? '+' : ''}${item.value}`}
            </Text>
          </View>
        )
      })}
    </View>
  )
}
