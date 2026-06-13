import { Text, View } from '@tarojs/components'
import type { Probability } from '@/services/mock'

export function ProbabilitySummary({ probabilities }: { probabilities: Probability[] }) {
  const maxValue = Math.max(...probabilities.map(item => item.value))

  return (
    <View className='probability-summary'>
      {probabilities.map(item => (
        <View
          key={item.label}
          className={`probability-summary__item ${item.value === maxValue ? 'probability-summary__item--primary' : ''}`}
        >
          <Text className='probability-summary__value'>{item.value}%</Text>
          <Text className='probability-summary__label'>{item.label}</Text>
        </View>
      ))}
    </View>
  )
}

