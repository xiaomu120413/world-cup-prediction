import { Text, View } from '@tarojs/components'
import type { Scoreline } from '@/services/mock'

export function ScorelineDistribution({ items }: { items: Scoreline[] }) {
  const max = Math.max(...items.map(item => item.probability))

  return (
    <View className='scorelines'>
      {items.map(item => (
        <View className='scoreline-row' key={item.score}>
          <Text className='scoreline-row__score'>{item.score}</Text>
          <View className='scoreline-row__track'>
            <View className='scoreline-row__bar' style={{ width: `${(item.probability / max) * 100}%` }} />
          </View>
          <Text className='scoreline-row__value'>{item.probability}%</Text>
        </View>
      ))}
    </View>
  )
}

